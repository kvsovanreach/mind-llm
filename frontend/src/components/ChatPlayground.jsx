import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Loader2,
  Copy,
  RotateCcw,
  Settings,
  Zap,
  MessageSquare,
  User,
  Bot,
  CheckCircle,
  Square,
  Sliders,
  Download,
  Upload,
  Trash2,
  Plus,
  ChevronDown,
  Terminal,
  Sparkles,
  History
} from 'lucide-react';

const ChatPlayground = ({ models, apiUrl, fetchWithAuth }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [streaming, setStreaming] = useState(true);
  const [loading, setLoading] = useState(false);
  const [apiKey, setApiKey] = useState(''); // Only used if fetchWithAuth not available
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(512);
  const [topP, setTopP] = useState(0.9);
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful assistant.');
  const [copiedId, setCopiedId] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [contextTruncated, setContextTruncated] = useState(false);
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  const textareaRef = useRef(null);

  // Fetch API keys on mount only if not using session auth
  useEffect(() => {
    if (fetchWithAuth) return; // Skip API key fetch when using session auth

    const fetchApiKeys = async () => {
      try {
        const res = await fetch(`${apiUrl}/api-keys`);
        const keys = await res.json();
        if (keys && keys.length > 0) {
          setApiKey(keys[0].key);
        } else {
          // Use a default API key if none exist
          setApiKey('default-api-key');
        }
      } catch (error) {
        console.error('Failed to fetch API keys:', error);
        // Use a default API key on error
        setApiKey('default-api-key');
      }
    };
    fetchApiKeys();
  }, [apiUrl, fetchWithAuth]);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Filter only running LLM models
  const availableModels = models.filter(m => m.type === 'llm' && m.status === 'running');

  // Set default model
  useEffect(() => {
    if (availableModels.length > 0 && !selectedModel) {
      setSelectedModel(availableModels[0].abbr);
    }
  }, [availableModels, selectedModel]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleStreamingResponse = async (userMessage, assistantMessage) => {
    const model = models.find(m => m.abbr === selectedModel);
    if (!model) return;

    try {
      abortControllerRef.current = new AbortController();

      // Construct the full URL - model.endpoint is like "/api/v1/qwen1.5b"
      // Need to ensure we're calling the absolute path
      const apiEndpoint = `${model.endpoint}/chat/completions`;
      console.log('Calling API endpoint:', apiEndpoint);
      console.log('Model:', model);
      console.log('Full URL will be:', window.location.origin + apiEndpoint);

      // Smart context management - truncate if too long
      const allMessages = [
        { role: 'system', content: systemPrompt },
        ...messages.filter(m => m.role !== 'system'),
        userMessage
      ];

      // Estimate tokens (rough: 1 token ≈ 4 characters)
      const estimateTokens = (msgs) => {
        return msgs.reduce((sum, msg) => sum + Math.ceil(msg.content.length / 4), 0);
      };

      // Truncate messages if needed (keep most recent)
      const modelMaxContext = 2048; // Qwen 1.5B limit
      let messagesToSend = [...allMessages];
      let estimatedTokens = estimateTokens(messagesToSend);

      // If too long, keep system + recent messages
      if (estimatedTokens + maxTokens > modelMaxContext - 50) { // 50 token buffer
        messagesToSend = [
          allMessages[0], // Keep system prompt
          ...allMessages.slice(-(Math.min(10, allMessages.length - 1))) // Keep last 10 messages
        ];

        // Further truncate if still too long
        while (estimateTokens(messagesToSend) + maxTokens > modelMaxContext - 50 && messagesToSend.length > 2) {
          messagesToSend.splice(1, 1); // Remove oldest non-system message
        }

        setContextTruncated(true);
      } else {
        setContextTruncated(false);
      }

      // Calculate safe max_tokens
      const inputTokens = estimateTokens(messagesToSend);
      const safeMaxTokens = Math.min(
        maxTokens,
        modelMaxContext - inputTokens - 50 // Leave buffer
      );

      console.log('Context management:', {
        originalMessages: allMessages.length,
        truncatedTo: messagesToSend.length,
        estimatedInputTokens: inputTokens,
        maxTokensRequested: maxTokens,
        safeMaxTokens: safeMaxTokens
      });

      // Use fetchWithAuth if available (logged in), otherwise use API key
      const requestBody = {
        messages: messagesToSend,
        stream: true,
        temperature,
        max_tokens: safeMaxTokens,
        top_p: topP
      };

      const response = fetchWithAuth
        ? await fetchWithAuth(apiEndpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody),
            signal: abortControllerRef.current.signal
          })
        : await fetch(apiEndpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-API-Key': apiKey
            },
            body: JSON.stringify(requestBody),
            signal: abortControllerRef.current.signal
          });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);
              const content = parsed.choices?.[0]?.delta?.content || '';
              if (content) {
                fullContent += content;
                setMessages(prev => {
                  const updated = [...prev];
                  const lastMsg = updated[updated.length - 1];
                  if (lastMsg && lastMsg.role === 'assistant') {
                    lastMsg.content = fullContent;
                  }
                  return updated;
                });
              }
            } catch (e) {
              console.error('Error parsing chunk:', e);
            }
          }
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Stream aborted');
      } else {
        console.error('Stream error:', error);
        setMessages(prev => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            lastMsg.content = 'Error: Failed to get response. Please check the model status.';
            lastMsg.error = true;
          }
          return updated;
        });
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !selectedModel || loading) return;

    const userMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString()
    };

    const assistantMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      model: selectedModel,
      streaming: streaming
    };

    setMessages(prev => [...prev, userMessage, assistantMessage]);
    setInput('');
    setLoading(true);

    await handleStreamingResponse(userMessage, assistantMessage);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const copyMessage = (content) => {
    navigator.clipboard.writeText(content);
    setCopiedId(content);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const clearChat = () => {
    setMessages([]);
  };

  const newConversation = () => {
    setMessages([]);
    setInput('');
  };

  const exportChat = () => {
    const data = {
      messages,
      model: selectedModel,
      timestamp: new Date().toISOString(),
      settings: { temperature, maxTokens, topP, systemPrompt }
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${Date.now()}.json`;
    a.click();
  };

  // Preset prompts
  const presetPrompts = [
    { icon: Terminal, label: 'Code Help', prompt: 'Help me write a Python function that...' },
    { icon: Sparkles, label: 'Creative Writing', prompt: 'Write a short story about...' },
    { icon: MessageSquare, label: 'Explain Concept', prompt: 'Explain quantum computing in simple terms...' },
    { icon: History, label: 'Summary', prompt: 'Summarize the following text...' }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="input w-64"
            disabled={loading}
          >
            {availableModels.length === 0 ? (
              <option value="">No models available</option>
            ) : (
              availableModels.map(model => (
                <option key={model.abbr} value={model.abbr}>
                  {model.name} ({model.abbr})
                </option>
              ))
            )}
          </select>

          <div className="flex items-center gap-2">
            <button
              onClick={newConversation}
              className="btn btn-secondary btn-sm"
              disabled={loading}
            >
              <Plus size={14} />
              New Chat
            </button>
            <button
              onClick={clearChat}
              className="btn btn-secondary btn-sm"
              disabled={loading || messages.length === 0}
            >
              <Trash2 size={14} />
              Clear
            </button>
            <button
              onClick={exportChat}
              className="btn btn-secondary btn-sm"
              disabled={messages.length === 0}
            >
              <Download size={14} />
              Export
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="btn btn-secondary btn-sm"
            >
              <Settings size={14} />
              Settings
              <ChevronDown size={14} className={`transition-transform ${showSettings ? 'rotate-180' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="card">
          <div className="card-body">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="form-group">
                <label className="label">Temperature</label>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={temperature}
                    onChange={(e) => setTemperature(Number(e.target.value))}
                    className="flex-1"
                  />
                  <span className="text-sm font-medium w-10">{temperature}</span>
                </div>
              </div>

              <div className="form-group">
                <label className="label">Max Tokens</label>
                <input
                  type="number"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                  min="1"
                  max="1900"
                  className="input"
                />
              </div>

              <div className="form-group">
                <label className="label">Top P</label>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={topP}
                    onChange={(e) => setTopP(Number(e.target.value))}
                    className="flex-1"
                  />
                  <span className="text-sm font-medium w-10">{topP}</span>
                </div>
              </div>

              <div className="form-group">
                <label className="label">Stream Response</label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={streaming}
                    onChange={(e) => setStreaming(e.target.checked)}
                    className="w-5 h-5"
                  />
                  <span className="text-sm">Enable streaming</span>
                </label>
              </div>
            </div>

            <div className="form-group mt-4">
              <label className="label">System Prompt</label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="input min-h-[80px]"
                placeholder="Set the behavior of the assistant..."
              />
            </div>
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="space-y-6">
        {/* Chat Messages */}
        <div>
          <div className="card h-[600px] flex flex-col">
            {messages.length === 0 ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <MessageSquare size={48} className="mx-auto mb-4 text-gray-400" />
                  <h3 className="text-heading-4 mb-2">Start a Conversation</h3>
                  <p className="text-small mb-6">Choose a model and start chatting</p>

                  {/* Preset Prompts */}
                  <div className="grid grid-cols-2 gap-3 max-w-md mx-auto">
                    {presetPrompts.map((preset, idx) => (
                      <button
                        key={idx}
                        onClick={() => setInput(preset.prompt)}
                        className="btn btn-secondary text-left"
                        disabled={!selectedModel}
                      >
                        <preset.icon size={16} />
                        <span className="text-sm">{preset.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                    {msg.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center">
                        <Bot size={18} className="text-blue-600 dark:text-blue-400" />
                      </div>
                    )}

                    <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-1' : ''}`}>
                      <div className={`rounded-lg p-4 ${
                        msg.role === 'user'
                          ? 'bg-blue-500 text-white'
                          : msg.error
                          ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400'
                          : 'bg-gray-800'
                      }`}>
                        <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>

                        {msg.role === 'assistant' && (
                          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                            <button
                              onClick={() => copyMessage(msg.content)}
                              className="btn btn-icon btn-ghost btn-sm"
                            >
                              {copiedId === msg.content ? (
                                <CheckCircle size={14} className="text-green-500" />
                              ) : (
                                <Copy size={14} />
                              )}
                            </button>
                            {msg.model && (
                              <span className="text-tiny">{msg.model}</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {msg.role === 'user' && (
                      <div className="w-8 h-8 rounded-lg bg-purple-100 dark:bg-purple-900/20 flex items-center justify-center order-2">
                        <User size={18} className="text-purple-600 dark:text-purple-400" />
                      </div>
                    )}
                  </div>
                ))}
                {loading && (
                  <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center">
                      <Bot size={18} className="text-blue-600 dark:text-blue-400" />
                    </div>
                    <div className="flex items-center gap-2">
                      <Loader2 size={16} className="animate-spin" />
                      <span className="text-small">Generating...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}

            {/* Input Area */}
            <div className="border-t border-gray-200 dark:border-gray-700 p-4">
              <div className="flex gap-3">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={selectedModel ? "Type your message... (Shift+Enter for new line)" : "Select a model first"}
                  className="input flex-1 min-h-[60px] max-h-[200px] resize-none"
                  disabled={!selectedModel || loading}
                />
                <div className="flex flex-col gap-2">
                  {loading ? (
                    <button
                      onClick={stopGeneration}
                      className="btn btn-danger"
                    >
                      <Square size={16} />
                      Stop
                    </button>
                  ) : (
                    <button
                      onClick={handleSend}
                      disabled={!input.trim() || !selectedModel}
                      className="btn btn-primary"
                    >
                      <Send size={16} />
                      Send
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default ChatPlayground;
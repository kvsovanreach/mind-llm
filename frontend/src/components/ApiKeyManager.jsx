import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import {
  Key,
  Plus,
  Trash2,
  Copy,
  CheckCircle,
  Eye,
  EyeOff,
  Loader2
} from 'lucide-react';

const ApiKeyManager = ({ apiKeys, onKeysUpdated, apiUrl, fetchWithAuth }) => {
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyDescription, setNewKeyDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);
  const [visibleKeys, setVisibleKeys] = useState(new Set());
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null);

  const createApiKey = async () => {
    if (!newKeyName.trim()) return;

    setCreating(true);
    try {
      const response = await fetchWithAuth(`${apiUrl}/api-keys?name=${encodeURIComponent(newKeyName)}&description=${encodeURIComponent(newKeyDescription)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        const data = await response.json();

        // Store the full key temporarily
        setNewlyCreatedKey(data.api_key);

        // Copy to clipboard with fallback
        copyToClipboardSafe(data.api_key);
        setCopiedKey(data.api_key);
        setTimeout(() => setCopiedKey(null), 5000);

        // Clear form
        setNewKeyName('');
        setNewKeyDescription('');

        // Refresh list
        onKeysUpdated();
      }
    } catch (error) {
      console.error('Failed to create API key:', error);
    } finally {
      setCreating(false);
    }
  };

  const deleteApiKey = async (key) => {
    setDeleting(key);
    try {
      const response = await fetchWithAuth(`${apiUrl}/api-keys/${key}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        onKeysUpdated();
        // Remove from visible keys if it was shown
        setVisibleKeys(prev => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }
    } catch (error) {
      console.error('Failed to delete API key:', error);
    } finally {
      setDeleting(null);
    }
  };

  const copyToClipboardSafe = async (text) => {
    try {
      // Try using the modern clipboard API first
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }

      // Fallback for older browsers or non-secure contexts
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      textArea.style.top = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      try {
        document.execCommand('copy');
        return true;
      } catch (err) {
        console.error('Failed to copy:', err);
        return false;
      } finally {
        textArea.remove();
      }
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);

      // Last resort: select the text for manual copying
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '50%';
      textArea.style.top = '50%';
      textArea.style.transform = 'translate(-50%, -50%)';
      textArea.style.zIndex = '9999';
      textArea.style.padding = '10px';
      textArea.style.border = '2px solid #007bff';
      textArea.style.borderRadius = '4px';
      textArea.style.backgroundColor = '#fff';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      // Show alert to manually copy
      alert('Please press Ctrl+C (or Cmd+C on Mac) to copy the API key, then click OK');

      setTimeout(() => {
        textArea.remove();
      }, 100);

      return false;
    }
  };

  const copyToClipboard = (text) => {
    copyToClipboardSafe(text);
    setCopiedKey(text);
    setTimeout(() => setCopiedKey(null), 3000);
  };

  const toggleKeyVisibility = (key) => {
    setVisibleKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const maskKey = (key) => {
    if (!key) return '••••••••';
    return key.substring(0, 8) + '••••••••••••••••';
  };

  return (
    <div className="space-y-6">
      {/* Create New Key */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            Create New API Key
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Key Name <span className="text-red-500">*</span>
                </label>
                <Input
                  placeholder="e.g., Production API Key"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && createApiKey()}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Description (Optional)
                </label>
                <Input
                  placeholder="e.g., Used for production app"
                  value={newKeyDescription}
                  onChange={(e) => setNewKeyDescription(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && createApiKey()}
                />
              </div>
            </div>

            <Button
              onClick={createApiKey}
              disabled={!newKeyName.trim() || creating}
              className="w-full md:w-auto"
            >
              {creating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  Create API Key
                </>
              )}
            </Button>
          </div>

          {/* Success message for newly created key */}
          {newlyCreatedKey && (
            <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-green-900">
                    API Key Created Successfully!
                  </p>
                  <p className="text-sm text-green-700 mt-1">
                    Your new API key has been copied to clipboard. Store it securely - you won't be able to see the full key again.
                  </p>
                  <div className="mt-2 p-2 bg-gray-800 rounded border border-green-600 font-mono text-sm break-all text-green-400">
                    {newlyCreatedKey}
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-2"
                    onClick={() => {
                      copyToClipboard(newlyCreatedKey);
                    }}
                  >
                    <Copy className="h-4 w-4 mr-2" />
                    Copy Again
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Existing Keys */}
      <Card>
        <CardHeader>
          <CardTitle>API Keys ({apiKeys.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {apiKeys.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Key className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p>No API keys yet. Create one to get started!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {apiKeys.map((apiKey) => (
                <div
                  key={apiKey.full_key || apiKey.key}
                  className="flex items-center justify-between p-4 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium">{apiKey.name}</span>
                      <Badge variant="outline" className="text-xs">
                        Active
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="text-sm text-gray-600 font-mono">
                        {visibleKeys.has(apiKey.full_key)
                          ? apiKey.full_key
                          : maskKey(apiKey.full_key || apiKey.key)}
                      </code>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleKeyVisibility(apiKey.full_key)}
                        className="h-6 w-6 p-0"
                      >
                        {visibleKeys.has(apiKey.full_key) ? (
                          <EyeOff className="h-3 w-3" />
                        ) : (
                          <Eye className="h-3 w-3" />
                        )}
                      </Button>
                      {visibleKeys.has(apiKey.full_key) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(apiKey.full_key)}
                          className="h-6 w-6 p-0"
                        >
                          {copiedKey === apiKey.full_key ? (
                            <CheckCircle className="h-3 w-3 text-green-600" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteApiKey(apiKey.full_key)}
                    disabled={deleting === apiKey.full_key}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    {deleting === apiKey.full_key ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Usage Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>How to Use Your API Key</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="font-medium mb-2">1. Include API Key in Request Headers</h4>
            <p className="text-sm text-gray-600 mb-2">Add your API key to the Authorization header as a Bearer token:</p>
            <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg text-sm overflow-x-auto">
              {`Authorization: Bearer YOUR_API_KEY`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium mb-2">2. cURL Example</h4>
            <p className="text-sm text-gray-600 mb-2">Make requests to any deployed model using cURL:</p>
            <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg text-sm overflow-x-auto">
{`curl -X POST http://localhost:9020/api/v1/MODEL_NAME/chat/completions \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "MODEL_NAME",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_tokens": 1000
  }'`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium mb-2">3. Python Example (OpenAI SDK)</h4>
            <p className="text-sm text-gray-600 mb-2">Use the OpenAI Python SDK with your deployed models:</p>
            <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg text-sm overflow-x-auto">
{`from openai import OpenAI

# Initialize client with your API endpoint
client = OpenAI(
    base_url="http://localhost:9020/api/v1/MODEL_NAME",
    api_key="YOUR_API_KEY"
)

# Make a chat completion request
response = client.chat.completions.create(
    model="MODEL_NAME",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    temperature=0.7,
    max_tokens=1000,
    stream=False  # Set to True for streaming responses
)

print(response.choices[0].message.content)`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium mb-2">4. JavaScript/TypeScript Example</h4>
            <p className="text-sm text-gray-600 mb-2">Make API calls from JavaScript/TypeScript applications:</p>
            <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg text-sm overflow-x-auto">
{`const response = await fetch('http://localhost:9020/api/v1/MODEL_NAME/chat/completions', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    model: 'MODEL_NAME',
    messages: [
      { role: 'system', content: 'You are a helpful assistant.' },
      { role: 'user', content: 'Hello!' }
    ],
    temperature: 0.7,
    max_tokens: 1000
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);`}
            </pre>
          </div>

          <div>
            <h4 className="font-medium mb-2">5. Available Endpoints</h4>
            <p className="text-sm text-gray-600 mb-2">Each deployed model exposes these OpenAI-compatible endpoints:</p>
            <div className="bg-gray-900 text-gray-100 p-3 rounded-lg text-sm">
              <div className="space-y-1">
                <div><span className="text-green-400">POST</span> /api/v1/MODEL_NAME/chat/completions - Chat completion</div>
                <div><span className="text-green-400">POST</span> /api/v1/MODEL_NAME/completions - Text completion</div>
                <div><span className="text-blue-400">GET</span> /api/v1/MODEL_NAME/models - List available models</div>
                <div><span className="text-blue-400">GET</span> /orchestrator/models - List all deployed models</div>
              </div>
            </div>
          </div>

          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h4 className="text-sm font-semibold text-blue-900 mb-1">Available Model Names</h4>
            <p className="text-sm text-blue-800">
              Replace MODEL_NAME with one of your deployed models (e.g., qwen1.5b, qwen3b, qwen7b, llama8b, etc.)
            </p>
          </div>

          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <h4 className="text-sm font-semibold text-yellow-900 mb-1">Security Best Practices</h4>
            <ul className="text-sm text-yellow-800 space-y-1 list-disc list-inside">
              <li>Never expose API keys in client-side code or public repositories</li>
              <li>Use environment variables to store API keys in your applications</li>
              <li>Rotate API keys regularly for production use</li>
              <li>Implement rate limiting and monitoring for your API usage</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ApiKeyManager;
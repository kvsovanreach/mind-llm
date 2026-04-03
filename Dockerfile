FROM vllm/vllm-openai:latest

# 1) Keep numpy compatible with numba (numba requires numpy <= 2.2)
RUN uv pip install --system --upgrade "numpy<=2.2"

# 2) Upgrade transformers for EXAONE (RopeParameters)
RUN uv pip install --system --upgrade "transformers>=5.0.0"

# 3) Ensure numba is installed/consistent (usually already present, but pinning helps)
RUN uv pip install --system --upgrade "numba"

import requests

ollama_url = 'http://13.222.51.51:11434'
model_name = 'llama3.2:1b'

print('Testing Ollama connection...')
print(f'URL: {ollama_url}')
print(f'Model: {model_name}')

# Test basic connectivity
try:
    response = requests.get(f'{ollama_url}/api/tags', timeout=5)
    print(f'Basic API test: {response.status_code}')
except Exception as e:
    print(f'Basic API failed: {e}')

# Test chat endpoint
try:
    chat_data = {
        'model': model_name,
        'messages': [{'role': 'user', 'content': 'Hello'}],
        'stream': False
    }

    response = requests.post(f'{ollama_url}/api/chat', json=chat_data, timeout=10)
    print(f'Chat API test: {response.status_code}')

    if response.status_code == 200:
        result = response.json()
        print('Chat response received successfully!')
        print(f'Response: {result.get("message", {}).get("content", "No content")}')
    else:
        print(f'Chat error: {response.text}')

except Exception as e:
    print(f'Chat API failed: {e}')

print('Test completed.')

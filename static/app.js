const form = document.querySelector('#form');
const button = document.querySelector('#generate');
const message = document.querySelector('#message');
const result = document.querySelector('#result');
const download = document.querySelector('#download');
const placeholder = document.querySelector('#placeholder');
const preview = document.querySelector('#preview');

async function checkConfig() {
  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error();
    const data = await response.json();
    document.querySelector('#key-status').textContent = data.configured
      ? '端点、密钥和模型已从 config.json 读取。'
      : `${data.error} 保存配置后请刷新页面。`;
    button.disabled = !data.configured;
  } catch {
    document.querySelector('#key-status').textContent = '无法连接本地服务，请重启程序并刷新页面。';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const prompt = document.querySelector('#prompt').value.trim();
  if (!prompt) {
    message.className = 'error';
    message.textContent = '请输入画面描述。';
    return;
  }
  button.disabled = true;
  button.textContent = '正在生成…';
  preview.setAttribute('aria-busy', 'true');
  message.className = '';
  message.textContent = '正在绘制，请耐心等待。图片生成与下载可能需要数分钟。';
  result.hidden = true;
  download.hidden = true;
  placeholder.hidden = false;
  try {
    const response = await fetch('/api/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt, size: document.querySelector('#size').value}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '生成失败，请稍后重试。');
    result.src = data.image_url;
    result.hidden = false;
    download.href = data.download_url;
    download.hidden = false;
    placeholder.hidden = true;
    message.textContent = '生成完成，图片已保存。';
  } catch (error) {
    message.className = 'error';
    message.textContent = error instanceof TypeError ? '连接中断，请检查本地程序是否仍在运行。' : error.message;
  } finally {
    button.disabled = false;
    button.textContent = '生成图片';
    preview.setAttribute('aria-busy', 'false');
  }
});

checkConfig();

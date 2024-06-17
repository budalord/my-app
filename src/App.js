import React, { useState, useEffect } from 'react';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './App.css'; // 引入自定义的CSS文件

function App() {
  const [url, setUrl] = useState('');
  const [downloadLink, setDownloadLink] = useState('');
  const [taskId, setTaskId] = useState('');
  const [progress, setProgress] = useState(0);

  const isValidUrl = (string) => {
    try {
      new URL(string);
      return true;
    } catch (_) {
      return false;
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setDownloadLink('');  // 清除之前的下载链接
    setProgress(0);  // 重置进度

    if (!url) {
      toast.error("URL cannot be empty!", { className: 'toast-custom-style' });
      return;
    }

    if (!isValidUrl(url)) {
      toast.error("Invalid URL format!", { className: 'toast-custom-style' });
      return;
    }

    const response = await fetch('http://0.0.0.0:8000/api/download', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url }),
    });

    if (response.ok) {
      const data = await response.json();
      setTaskId(data.task_id);
      toast.success("Analysis started!", { className: 'toast-custom-style' });
    } else {
      const errorData = await response.json();
      toast.error(`Analysis failed: ${errorData.detail}`, { className: 'toast-custom-style' });
    }
  };

  const handleReset = () => {
    setUrl('');
    setDownloadLink('');
    setProgress(0);
    setTaskId('');
    toast.info("Input reset successfully!");
  };

  const handleDownloadComplete = async () => {
    // 通知后端清理文件
    await fetch(`http://0.0.0.0:8000/api/cleanup/${taskId}`, {
      method: 'POST',
    });
    toast.info("Files cleaned up successfully!");
  };

  useEffect(() => {
    if (taskId) {
      const interval = setInterval(async () => {
        const response = await fetch(`http://0.0.0.0:8000/api/progress/${taskId}`);
        if (response.ok) {
          const data = await response.json();
          console.log(`Progress: ${data.progress}%`); // 添加日志
          setProgress(data.progress);
          if (data.progress === 100) {
            clearInterval(interval);
            const checkFileExists = async () => {
              const fileResponse = await fetch(`http://0.0.0.0:8000/api/file/${taskId}`);
              if (fileResponse.ok) {
                const blob = await fileResponse.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                setDownloadLink(downloadUrl);
                toast.success("Analysis complete!", { className: 'toast-custom-style' });
              } else {
                setTimeout(checkFileExists, 1000); // 如果文件还没有准备好，1秒后再次检查
              }
            };
            checkFileExists();
          }
        }
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [taskId, url]);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Video Downloader（<span className="subtitle">Cool</span>Cat 专属）<span></span></h1>
        <form onSubmit={handleSubmit} className="download-form">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Enter video URL"
            className="url-input"
          />
          <button type="button" className="reset-button" onClick={handleReset}>Reset</button>
          <button type="submit" className="download-button">Analysis</button>
        </form>
        {progress > 0 && progress < 100 && (
          <div className="progress-container">
            <div className="progress-bar" style={{ width: `${progress}%` }}></div>
            <span>{progress}%</span>
          </div>
        )}
        {downloadLink && (
          <a href={downloadLink} download="video.mp4" className="download-link" onClick={handleDownloadComplete}>
            Download Here
          </a>
        )}
        <ToastContainer />
      </header>
    </div>
  );
}

export default App;

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import time
import re
import logging
import uvicorn
import py7zr

app = FastAPI()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置 CORS 设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FFMPEG_ZIP_PATH = os.path.abspath("tmp/ffmpeg/ffmpeg.7z")  # 本地 ffmpeg 安装包路径
FFMPEG_EXTRACT_DIR = "/tmp/ffmpeg"  # 解压路径
FFMPEG_EXE_PATH = os.path.join(FFMPEG_EXTRACT_DIR, "ffmpeg.exe").replace("\\", "/")
DOWNLOAD_PATH = "./tmp/downloads"  # 在 Vercel 上使用临时目录

progress = {}
tasks = {}
downloads_complete = {}

def extract_ffmpeg():
    if not os.path.exists(FFMPEG_EXTRACT_DIR):
        os.makedirs(FFMPEG_EXTRACT_DIR, exist_ok=True)
        with py7zr.SevenZipFile(FFMPEG_ZIP_PATH, mode='r') as archive:
            archive.extractall(path=FFMPEG_EXTRACT_DIR)
        
        # 查找解压后的 ffmpeg 可执行文件
        for root, dirs, files in os.walk(FFMPEG_EXTRACT_DIR):
            if 'ffmpeg.exe' in files:
                ffmpeg_exe_path = os.path.join(root, 'ffmpeg.exe')
                return ffmpeg_exe_path.replace("\\", "/")
    
    return FFMPEG_EXE_PATH

FFMPEG_PATH = "./tmp/ffmpeg/bin/ffmpeg.exe"

# 添加ffmpeg路径到环境变量
os.environ["PATH"] += os.pathsep + os.path.dirname(FFMPEG_PATH)

class DownloadRequest(BaseModel):
    url: str

def download_video_file(task_id: str, url: str):
    global progress, tasks, downloads_complete
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_PATH, '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'quiet': False,
        'ffmpeg_location': FFMPEG_PATH,  # 使用动态下载的ffmpeg路径
        'progress_hooks': [lambda d: update_progress(task_id, d)],
    }

    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    # 验证FFMPEG路径
    logger.info(f"FFMPEG path: {FFMPEG_PATH}")
    logger.info(f"Is FFMPEG executable: {os.access(FFMPEG_PATH, os.X_OK)}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            video_title = result['title']
            video_ext = result['ext']
            downloaded_file_path = os.path.join(DOWNLOAD_PATH, f"{video_title}.{video_ext}").replace("\\", "/")
            tasks[task_id] = downloaded_file_path
            progress[task_id] = 100  # 下载完成
            downloads_complete[task_id] = False
            return downloaded_file_path
    except Exception as e:
        progress[task_id] = -1
        logger.error(f"Error downloading video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def update_progress(task_id, d):
    global progress
    if d['status'] == 'downloading':
        percent_str = re.sub(r'\x1b\[.*?m', '', d['_percent_str'])  # 移除ANSI转义码
        progress[task_id] = float(percent_str.strip('%'))
    elif d['status'] == 'finished':
        progress[task_id] = 100

@app.post("/api/download")
async def download_video(download_request: DownloadRequest, background_tasks: BackgroundTasks):
    try:
        task_id = str(int(time.time()))  # 使用时间戳作为任务ID
        progress[task_id] = 0  # 初始化任务进度
        tasks[task_id] = None  # 初始化任务文件路径
        background_tasks.add_task(download_video_file, task_id, download_request.url)
        return {"task_id": task_id}
    except Exception as e:
        logger.error(f"Error starting download: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    if task_id in progress:
        return {"progress": progress[task_id]}
    else:
        logger.error(f"Task ID {task_id} not found")
        raise HTTPException(status_code=404, detail="Task not found")

@app.get("/api/file/{task_id}")
async def get_file(task_id: str):
    if task_id in tasks and tasks[task_id]:
        file_path = tasks[task_id]
        if os.path.exists(file_path):
            return FileResponse(file_path, filename=os.path.basename(file_path))
        else:
            logger.error(f"File {file_path} not found")
            raise HTTPException(status_code=404, detail="File not found")
    else:
        logger.error(f"Task ID {task_id} not completed yet")
        raise HTTPException(status_code=404, detail="Task not completed yet")

@app.post("/api/cleanup/{task_id}")
async def cleanup_file(task_id: str):
    if task_id in tasks:
        file_path = tasks[task_id]
        if os.path.exists(file_path):
            os.remove(file_path)
        tasks.pop(task_id, None)
        progress.pop(task_id, None)
        downloads_complete.pop(task_id, None)
        logger.info(f"File {file_path} cleaned up successfully!")
        return {"message": "File cleaned up successfully!"}
    else:
        logger.error(f"Task ID {task_id} not found for cleanup")
        raise HTTPException(status_code=404, detail="Task not found")

def run():
    uvicorn.run(app, host="0.0.0.0", port=8000)

# For Vercel serverless
async def vercel_app(scope, receive, send):
    await app(scope, receive, send)

if __name__ == "__main__":
    run()

@echo off
echo 正在安装依赖...
pip install -r requirements.txt
echo.
echo 启动智能交通预测API服务...
echo 服务将在 http://127.0.0.1:8003 上运行
echo 按 Ctrl+C 停止服务
echo.
python server.py
pause
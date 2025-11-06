#!/bin/bash
# 启动前端HTTP服务器

echo "🌐 启动SeenFetch前端服务器..."
echo "📂 服务目录: services/web"
echo "🔗 访问地址: http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "================================"

cd services/web
python3 -m http.server 3000

# 1) 启动后端
conda activate WordLine
cd backend
python src/server.py

# 2) 启动前端
conda activate WordLine
cd ..\frontend
npm i
npm run dev
import uvicorn
import sys
import io



if __name__ == "__main__":
    # 这里的 "app.main:app" 意思是：去 app 文件夹下的 main.py 里找一个叫 app 的变量
    # reload=True 表示你改了代码保存后，服务器会自动重启，不用你手动关了再开
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
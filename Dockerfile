# 基于镜像基础
FROM python:slim-buster
  
# 设置代码文件夹工作目录 /app
COPY . /media_flow
WORKDIR /media_flow

RUN pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

CMD ["python3","main.py" ]

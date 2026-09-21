FROM gcc:13

# gfortran（gcc 镜像自带）+ python3，用于双端执行数值等价验证
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-numpy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /io

# 运行时用 --network none --read-only --memory 512m --cpus 1 限制
ENTRYPOINT ["/bin/bash", "-c"]

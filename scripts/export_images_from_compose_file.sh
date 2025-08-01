#!/bin/bash

# 检查是否提供了 docker-compose 文件路径
if [ $# -eq 0 ]; then
    echo "Usage: $0 <docker-compose-file> [output-dir]"
    exit 1
fi

COMPOSE_FILE=$1
OUTPUT_DIR=${2:-./saved_images}

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 获取当前目录名作为默认项目名
DEFAULT_PROJECT_NAME=$(basename "$(pwd)")

# 获取所有服务使用的镜像
IMAGES=$(docker-compose -f "$COMPOSE_FILE" -p "$DEFAULT_PROJECT_NAME" config | grep 'image:' | awk '{print $2}' | sort | uniq)

if [ -z "$IMAGES" ]; then
    echo "No images found in the docker-compose file."
    exit 1
fi

echo "Found the following images in $COMPOSE_FILE:"
echo "$IMAGES"

# 保存每个镜像
for IMAGE in $IMAGES; do
    echo "Saving $IMAGE..."
    # 替换特殊字符为下划线用于文件名
    FILENAME=$(echo "$IMAGE" | sed 's/[\/:]/-/g').tar
    docker save -o "$OUTPUT_DIR/$FILENAME" "$IMAGE"
    if [ $? -ne 0 ]; then
        echo "Failed to save $IMAGE"
        exit 1
    fi
done

echo "All images saved to $OUTPUT_DIR"

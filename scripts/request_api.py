#!/usr/bin/env python3
"""
测试新的文档上传和解析API

此脚本测试以下接口的新规范：
1. POST /upload_documents - 上传文档（现在需要chunk_method、parser_flag、parser_config）
2. POST /analyzing_documents - 获取文档分块结果（现在只需要dataset_id、document_id、document_name）
3. POST /chunk_text - 直接文本分块（保持不变）

测试场景：
- 文件上传：使用URL文件路径 + naive分块方法
- 文本上传：使用直接文本内容 + book分块方法
- 文本分块：使用laws分块方法
"""

import json
import time

import click
import requests


def test_upload_and_analyze(base_url, file_path):
    """测试上传文档并解析"""
    # 测试文档上传（使用文件路径，naive分块方法，启用解析配置）
    upload_data = {
        "file_path": file_path,
        "chunk_method": "naive",  # 基础解析方法
        "parser_flag": 1,  # 启用解析配置
        "parser_config": {
            "chunk_token_count": 128,
            "layout_recognize": True,
            "delimiter": "\n",
        },
    }

    print("1. 上传文档...")
    print(f"   请求参数: {json.dumps(upload_data, indent=2, ensure_ascii=False)}")
    response = requests.post(f"{base_url}/upload_documents", json=upload_data)

    if response.status_code != 200:
        print(f"上传失败: {response.status_code} - {response.text}")
        return

    upload_result = response.json()
    print(f"上传成功: {json.dumps(upload_result, indent=2, ensure_ascii=False)}")

    document_id = upload_result["document_id"]
    part_document_id = upload_result["part_document_id"]

    # 等待后台处理完成
    print("\n2. 等待后台处理完成...")
    for i in range(10):
        time.sleep(10)  # 给后台处理一些时间

        # 测试获取完整结果
        analyze_data = {
            "dataset_id": upload_result["dataset_id"],
            "document_id": document_id,
            "document_name": upload_result["document_name"],
        }

        print("\n3. 获取完整解析结果...")
        response = requests.post(f"{base_url}/analyzing_documents", json=analyze_data)

        if response.status_code == 200:
            result = response.json()
            print(f"解析成功，共{len(result['chunks'])}个分块")
            print("前3个分块预览:")
            for i, chunk in enumerate(result["chunks"][:3]):
                print(f"  分块{i + 1}: {chunk[:100]}...")
            break

    if response.status_code != 200:
        print(f"解析失败: {response.status_code} - {response.text}")

    # 测试获取部分结果（快速展示）
    analyze_partial_data = {
        "dataset_id": upload_result["dataset_id"],
        "document_id": part_document_id,
        "document_name": upload_result["part_document_name"],
    }

    print("\n4. 获取部分解析结果（快速展示）...")
    response = requests.post(
        f"{base_url}/analyzing_documents", json=analyze_partial_data
    )

    if response.status_code == 200:
        result = response.json()
        print(f"部分解析成功，共{len(result['chunks'])}个分块")
        print("前3个分块预览:")
        for i, chunk in enumerate(result["chunks"][:3]):
            print(f"  分块{i + 1}: {chunk[:100]}...")
    else:
        print(f"部分解析失败: {response.status_code} - {response.text}")


def test_text_chunking(base_url):
    """测试文本分块（使用chunk_text接口）"""

    test_text = """
    中华人民共和国网络安全法是为了保障网络安全，维护网络空间主权和国家安全、社会公共利益，
    保护公民、法人和其他组织的合法权益，促进经济社会信息化健康发展，制定的法律。

    由全国人民代表大会常务委员会于2016年11月7日发布，自2017年6月1日起施行。

    目录
    第一章 总则
    第二章 网络安全支持与促进
    第三章 网络运行安全
    第一节 一般规定
    第二节 关键信息基础设施的运行安全
    第四章 网络信息安全
    第五章 监测预警与应急处置
    第六章 法律责任
    第七章 附则

    第一章 总则
    第一条 为了保障网络安全，维护网络空间主权和国家安全、社会公共利益，
    保护公民、法人和其他组织的合法权益，促进经济社会信息化健康发展，制定本法。

    第二条 在中华人民共和国境内建设、运营、维护和使用网络，
    以及网络安全的监督管理，适用本法。
    """

    chunk_data = {
        "text": test_text,
        "chunk_method": "laws",  # 法律文档解析方法，适合法律条文
        "parser_flag": 1,  # 启用解析配置
        "parser_config": {
            "chunk_token_count": 50,  # 小分块以便观察效果
            "delimiter": "\n",
        },
    }

    print("\n5. 测试文本分块（chunk_text接口）...")
    response = requests.post(f"{base_url}/chunk_text", json=chunk_data)

    if response.status_code == 200:
        result = response.json()
        print(f"文本分块成功，共{len(result['chunks'])}个分块")
        for i, chunk in enumerate(result["chunks"]):
            print(f"  分块{i + 1}: {chunk}")
    else:
        print(f"文本分块失败: {response.status_code} - {response.text}")


def test_content_upload_and_analyze(base_url):
    """测试文本内容上传和解析（使用upload_documents和analyzing_documents接口）"""

    test_text = """
    区块链技术是一种分布式数据库技术，具有去中心化、透明、不可篡改等特点。
    它最初作为比特币的底层技术而被人们所知，但现在已经扩展到许多其他领域。

    区块链的核心概念包括：
    1. 去中心化：没有单一的控制点，数据分布在网络中的多个节点上
    2. 透明性：所有交易都是公开可见的
    3. 不可篡改：一旦数据被记录在区块中，就很难被更改
    4. 共识机制：网络中的节点通过特定的算法达成一致

    区块链的应用领域：
    - 数字货币：比特币、以太坊等加密货币
    - 供应链管理：追踪产品从生产到消费的整个过程
    - 智能合约：自动执行合约条款的程序
    - 数字身份：安全的身份验证和管理
    - 投票系统：透明和防篡改的电子投票

    区块链技术仍在快速发展中，未来可能会在更多领域发挥重要作用。
    """

    # 1. 上传文本内容（使用book分块方法，适合结构化文档）
    upload_data = {
        "content": test_text,
        "chunk_method": "naive",  # 书籍格式解析，适合结构化内容
        "parser_flag": 1,  # 启用解析配置
        "parser_config": {
            "chunk_token_count": 256,  # 更大的分块大小
            "layout_recognize": True,
            "delimiter": "\n\n",  # 按段落分隔
        },
    }

    print("\n6. 上传文本内容...")
    response = requests.post(f"{base_url}/upload_documents", json=upload_data)

    if response.status_code != 200:
        print(f"内容上传失败: {response.status_code} - {response.text}")
        return

    upload_result = response.json()
    print(f"内容上传成功: {json.dumps(upload_result, indent=2, ensure_ascii=False)}")

    document_id = upload_result["document_id"]
    part_document_id = upload_result["part_document_id"]

    # 2. 等待后台处理完成并获取完整结果
    print("\n7. 等待后台处理完成并获取完整解析结果...")
    for i in range(10):
        time.sleep(10)  # 给后台处理一些时间

        # 获取完整结果
        analyze_data = {
            "dataset_id": upload_result["dataset_id"],
            "document_id": document_id,
            "document_name": upload_result["document_name"],
        }

        response = requests.post(f"{base_url}/analyzing_documents", json=analyze_data)

        if response.status_code == 200:
            result = response.json()
            print(f"完整解析成功，共{len(result['chunks'])}个分块")
            print("前3个分块预览:")
            for i, chunk in enumerate(result["chunks"][:3]):
                print(f"  分块{i + 1}: {chunk[:100]}...")
            break
        else:
            result = response.json()
            if "Document is being parsed" in str(result.get("chunks", [])):
                print(
                    f"  解析进度: {result['chunks'][0] if result.get('chunks') else '处理中...'}"
                )
                continue
            else:
                print(f"完整解析失败: {response.status_code} - {response.text}")
                break

    # 3. 获取部分结果（快速展示）
    analyze_partial_data = {
        "dataset_id": upload_result["dataset_id"],
        "document_id": part_document_id,
        "document_name": upload_result["part_document_name"],
    }

    print("\n8. 获取部分解析结果（快速展示）...")
    response = requests.post(
        f"{base_url}/analyzing_documents", json=analyze_partial_data
    )

    if response.status_code == 200:
        result = response.json()
        print(f"部分解析成功，共{len(result['chunks'])}个分块")
        print("前3个分块预览:")
        for i, chunk in enumerate(result["chunks"][:3]):
            print(f"  分块{i + 1}: {chunk[:100]}...")
    else:
        print(f"部分解析失败: {response.status_code} - {response.text}")


@click.command()
@click.option("--base-url", default="http://localhost:5001", help="API服务器基础URL")
@click.option(
    "--file-path",
    default="https://raw.githubusercontent.com/rstudio/cheatsheets/main/data-visualization.pdf",
    help="要上传的文件路径或URL",
)
@click.option(
    "--mode",
    type=click.Choice(["upload", "chunk", "content", "both", "all"]),
    default="all",
    help="测试模式: upload(仅文件上传), chunk(仅chunk_text分块), content(仅文本内容上传), both(文件上传+chunk_text), all(所有测试)",
)
def main(base_url, file_path, mode):
    """测试新的文档上传和解析API"""
    print("测试新的文档上传和解析API")
    print("=" * 50)
    print(f"基础URL: {base_url}")
    print(f"文件路径: {file_path}")
    print(f"测试模式: {mode}")
    print()

    try:
        if mode in ["upload", "both", "all"]:
            test_upload_and_analyze(base_url, file_path)

        if mode in ["chunk", "both", "all"]:
            test_text_chunking(base_url)

        if mode in ["content", "all"]:
            test_content_upload_and_analyze(base_url)

    except Exception as e:
        print(f"测试过程中出现错误: {e}")


if __name__ == "__main__":
    main()

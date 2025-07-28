#!/usr/bin/env python3
"""
测试新的文档上传和解析API
"""

import json
import time

import click
import requests


def test_upload_and_analyze(base_url, file_path):
    """测试上传文档并解析"""
    # 测试文档上传
    upload_data = {"file_path": file_path}

    print("1. 上传文档...")
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
            "chunk_method": "naive",
            "parser_flag": 0,
            "parser_config": {},
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
        "chunk_method": "naive",
        "parser_flag": 0,
        "parser_config": {},
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
    """测试文本分块"""

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
        "chunk_method": "naive",
        "parser_flag": 1,
        "parser_config": {"chunk_token_count": 50, "delimiter": "\n"},
    }

    print("\n5. 测试文本分块...")
    response = requests.post(f"{base_url}/chunk_text", json=chunk_data)

    if response.status_code == 200:
        result = response.json()
        print(f"文本分块成功，共{len(result['chunks'])}个分块")
        for i, chunk in enumerate(result["chunks"]):
            print(f"  分块{i + 1}: {chunk}")
    else:
        print(f"文本分块失败: {response.status_code} - {response.text}")


@click.command()
@click.option("--base-url", default="http://localhost:5001", help="API服务器基础URL")
@click.option(
    "--file-path",
    default="https://raw.githubusercontent.com/rstudio/cheatsheets/main/data-visualization.pdf",
    help="要上传的文件路径或URL",
)
@click.option(
    "--mode",
    type=click.Choice(["upload", "chunk", "both"]),
    default="both",
    help="测试模式: upload(仅上传), chunk(仅分块), both(两者都测试)",
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
        if mode in ["upload", "both"]:
            test_upload_and_analyze(base_url, file_path)

        if mode in ["chunk", "both"]:
            test_text_chunking(base_url)

    except Exception as e:
        print(f"测试过程中出现错误: {e}")


if __name__ == "__main__":
    main()

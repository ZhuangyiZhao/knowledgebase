# 1. Enterprise RAG System

## 1.1 目录

- [1. Enterprise RAG System](#1-enterprise-rag-system)
  - [1.1 目录](#11-目录)
  - [1.2 Run](#12-run)
  - [1.3 Structure](#13-structure)
  - [1.4 Next](#14-next)
  - [1.5 Reference](#15-reference)
  - [1.6 Notes](#16-notes)

本项目是企业知识库 RAG 系统的轻量代码骨架，覆盖文档导入、切片、索引、混合检索、引用回答和离线评测。

## 1.2 Run

```bash
python3 -m rag_app.main ingest
python3 -m rag_app.main ask "Redis 缓存击穿怎么处理？"
python3 -m rag_app.main search "慢 SQL 为什么没有走索引？"
python3 -m rag_app.main eval
```

## 1.3 Structure

```text
rag_app/
  chunker.py      文档切片
  embedding.py    本地哈希向量
  ingest.py       文档导入和索引构建
  retriever.py    混合检索
  generator.py    引用回答
  evaluator.py    Recall@5 评测
  main.py         CLI 入口
data/
  docs/           示例文档
  eval/           示例评测集
  index.json      本地索引文件
```

## 1.4 Next

后续生产化替换点：

- `embedding.py` 替换为真实 Embedding 模型。
- `index.json` 替换为 PostgreSQL + pgvector 或 Milvus。
- `generator.py` 替换为真实 LLM 调用。
- `retriever.py` 增加 BM25、Rerank、metadata filter 和缓存。

## 1.5 Reference

## 1.6 Notes

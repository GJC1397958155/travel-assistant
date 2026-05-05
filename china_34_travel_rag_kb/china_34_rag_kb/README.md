# 中国34省级行政区旅游RAG知识库（LangChain项目版）

## 数据规模
- 覆盖：中国34个省级行政区
- 代表旅游城市：34个
- 每个城市：至少5个著名景点
- 景点文档：170篇
- 城市基础文档：34篇
- 行程模板文档：34篇
- metadata记录：238条

## 目录说明
- city_docs/：城市基础档案，包含城市简介、季节、交通、住宿、美食、避坑、工具类知识、标签体系
- attraction_docs/：景点知识库，包含景点介绍、开放时间/门票校验策略、游玩时长、打卡机位、配套、适合人群、避坑
- route_docs/：1日/2日/3日/亲子/情侣/老人/徒步/懒人路线模板
- metadata.jsonl：用于Chroma/Qdrant/Milvus的过滤字段
- testset.json：RAG评估测试集
- build_chroma_index.py：LangChain + Chroma建库示例
- hybrid_search_chroma_bm25.py：Chroma + BM25 类混合检索示例

## 重要设计说明
本知识库适合简历项目和Demo，不建议把开放时间、门票价格、签证/通行政策、防疫政策、实时交通写死。
这些属于动态字段，正式系统应通过：
- 景区官网/官方小程序
- 12306/机场/航司
- 地图API
- 天气API
- 实时搜索工具
进行校验。

## 推荐RAG检索方式
1. 先基于metadata过滤：city、region、people、days、budget、transport
2. 再做向量检索
3. 对关键词强的问题使用BM25补召回
4. 最后用rerank或LLM重排

## 推荐chunk策略
- 城市档案：按二级标题切
- 景点文档：一个景点作为一个主chunk，必要时按“路线/避坑/配套”拆分
- 行程模板：一个路线版本一个chunk
- chunk_size：700-1000
- chunk_overlap：100-150

## 简历写法
基于LangChain构建覆盖中国34个省级行政区的旅游RAG知识库，包含城市档案、景点信息、路线模板、美食住宿和避坑干货；设计metadata标签体系，支持按城市、季节、天数、人群、预算和出行方式进行精准过滤，并结合Chroma向量检索与BM25关键词召回实现混合检索。

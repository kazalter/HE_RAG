"""chunker 单测：章节识别、目录清理、长段切分、小 chunk 合并。

全部是纯文本处理，不加载 embedding 模型。
"""

from src import chunker


# --- 章节识别 is_heading --------------------------------------------------

def test_is_heading_recognizes_chinese_and_numeric():
    assert chunker.is_heading("第一章 绪论")
    assert chunker.is_heading("1.2 系统设计")
    assert chunker.is_heading("摘要")
    assert chunker.is_heading("参考文献")


def test_is_heading_rejects_body_text():
    # 超过 40 字的正文不是标题
    assert not chunker.is_heading("这是一段比较长的正文内容用来测试标题判定逻辑是否会误判正文" * 2)
    # “编号.词：正文”形如带冒号的描述句，不是标题
    assert not chunker.is_heading("1.介绍：本文研究的主要内容与方法")
    # 含制表符的目录残留不是标题
    assert not chunker.is_heading("第一章 绪论\t3")
    assert not chunker.is_heading("普通的一段话")


# --- 目录清理 remove_table_of_contents ------------------------------------

def test_remove_table_of_contents_strips_toc_lines():
    paragraphs = [
        "目录",
        "第一章 绪论........................3",
        "1.1 研究背景\t5",
        "第一章 绪论",
        "这是正文段落。",
    ]
    cleaned = chunker.remove_table_of_contents(paragraphs)

    assert "目录" not in cleaned                  # 目录标题被删
    assert "这是正文段落。" in cleaned             # 正文保留
    assert "第一章 绪论" in cleaned                # 真正的章节标题（无页码）保留
    assert all("....." not in p for p in cleaned)  # 点线目录行被删
    assert all("\t" not in p for p in cleaned)     # 制表符页码行被删


# --- 长段切分 split_long_paragraph ----------------------------------------

def test_split_long_paragraph_by_sentence_boundary():
    paragraph = "这是一句话。" * 100  # 600 字，按句号可切
    parts = chunker.split_long_paragraph(paragraph, max_size=100)

    assert len(parts) > 1
    assert all(len(part) <= 100 for part in parts)


def test_split_long_paragraph_hard_splits_oversized_sentence():
    paragraph = "啊" * 250  # 无句末标点的超长单句
    parts = chunker.split_long_paragraph(paragraph, max_size=100)

    assert all(len(part) <= 100 for part in parts)
    assert "".join(parts) == paragraph  # 硬切不丢字


# --- 小 chunk 合并 merge_small_chunks -------------------------------------

def test_merge_small_chunks_combines_same_section():
    chunks = [
        {"source": "a.txt", "section_title": "第一章", "text": "短" * 10, "char_count": 10},
        {"source": "a.txt", "section_title": "第一章", "text": "也短" * 10, "char_count": 20},
    ]
    merged = chunker.merge_small_chunks(chunks)

    assert len(merged) == 1
    assert merged[0]["char_count"] == len(merged[0]["text"])


def test_merge_small_chunks_respects_hard_boundary():
    # “摘要”是硬边界，不能与正文章节合并，即使两段都很短
    chunks = [
        {"source": "a.txt", "section_title": "摘要", "text": "短" * 10, "char_count": 10},
        {"source": "a.txt", "section_title": "第一章", "text": "正" * 10, "char_count": 10},
    ]
    merged = chunker.merge_small_chunks(chunks)

    assert len(merged) == 2


def test_merge_small_chunks_does_not_cross_source():
    chunks = [
        {"source": "a.txt", "section_title": "第一章", "text": "短" * 10, "char_count": 10},
        {"source": "b.txt", "section_title": "第一章", "text": "短" * 10, "char_count": 10},
    ]
    merged = chunker.merge_small_chunks(chunks)

    assert len(merged) == 2

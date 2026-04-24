"""
detector.py - V8 学术论文检测引擎
4层检测 + DOI-Title 验证，从 V7 monitor.py 重构
"""

import os
import re
import json
import hashlib
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
import pdfplumber

# ========== MD5 去重 ==========

def md5_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

# ========== DOI 提取 ==========

def extract_doi_from_filename(filename):
    """从文件名提取DOI"""
    name_no_ext = Path(filename).stem
    doi_match = re.search(r'(10\.\d{4,9}(?:/[-._;()/:A-Z0-9a-z]+)?[-._;()/:A-Z0-9a-z]+)', name_no_ext)
    if not doi_match:
        return None
    doi = doi_match.group(1)
    doi = re.sub(r'/$', '', doi)
    doi = re.sub(r'\(\d+\)$', '', doi)
    if '/' not in doi[10:]:
        doi = re.sub(r'^(10\.\d{4})([a-zA-Z0-9_.\-]+)', r'\1/\2', doi)
    elif '/' in doi[10:]:
        parts = doi.split('/')
        doi = parts[0] + '/' + parts[1]
    return doi

# ========== OpenAlex API ==========

def query_metadata_by_doi(doi):
    """通过DOI查询OpenAlex"""
    api_url = f"https://api.openalex.org/works/doi:{doi}"
    try:
        req = urllib.request.Request(api_url, headers={'Accept': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        if not data.get('title'):
            return None
        authors = [a['author']['display_name'] for a in data.get('authorships', [])[:3]]
        abstract = data.get('abstract_inverted_index', None)
        abstract_text = None
        if abstract:
            words = sorted(abstract.items(), key=lambda x: x[0])
            abstract_text = ' '.join(w for w, _ in words)
        return {
            "status": "success", "doi": doi, "confidence": "high",
            "title": data["title"], "authors": authors,
            "journal": data.get('primary_location', {}).get('source', {}).get('display_name'),
            "year": data.get('publication_year'), "abstract": abstract_text
        }
    except Exception:
        return None

def query_metadata_by_title(title):
    """用标题搜索OpenAlex"""
    try:
        encoded = urllib.parse.quote(title.strip())
        api_url = f"https://api.openalex.org/works?title={encoded}&per_page=1"
        req = urllib.request.Request(api_url, headers={'Accept': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        results = data.get('results', [])
        if not results:
            return None
        r = results[0]
        doi = r.get('doi', '').replace('https://doi.org/', '')
        abstract = r.get('abstract_inverted_index', None)
        abstract_text = None
        if abstract:
            words = sorted(abstract.items(), key=lambda x: x[0])
            abstract_text = ' '.join(w for w, _ in words)
        authors = [a['author']['display_name'] for a in r.get('authorships', [])[:3]]
        return {
            "status": "title_search", "doi": doi, "confidence": "low",
            "title": r.get('title'), "authors": authors,
            "journal": r.get('primary_location', {}).get('source', {}).get('display_name'),
            "year": r.get('publication_year'), "abstract": abstract_text
        }
    except Exception:
        return None

# ========== PDF 标题提取 ==========

def extract_pdf_title(src):
    """从PDF第1页提取标题 — 基于字号（标题通常最大）"""
    try:
        with pdfplumber.open(src) as pdf:
            page = pdf.pages[0]
            words = page.extract_words()

        if not words:
            return None

        # 找出最大字号（通常为标题）— 使用 height 字段
        # 某些PDF可能直接提供 size，兼容两种情况
        max_font = max(w.get('size', w['height']) for w in words)
        # 允许 10% 容差，收集接近最大字号的词
        threshold = max_font * 0.85
        title_words = [w for w in words if w.get('size', w['height']) >= threshold]

        if not title_words:
            return None

        # 排除纯数字/短碎片（页码、卷号等）
        skip = {'vol', 'vol.', 'issue', 'pp.', 'pp', 'fig', 'fig.',
                'suppl', 'no.', 'no', 'jan', 'feb', 'mar', 'apr',
                'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
                '2024', '2025', '2026', '2027'}
        title_words = [w for w in title_words if w['text'].lower() not in skip]

        # 按 y 坐标排序（行序），再按 x 坐标排序（行内词序）
        title_words.sort(key=lambda w: (round(w['top'], 1), w['x0']))

        # 合并为文本
        title_text = ' '.join(w['text'] for w in title_words)
        # 清理多余空格
        import re as _re
        title_text = _re.sub(r'\s+', ' ', title_text).strip()

        if 15 < len(title_text) < 500:
            return title_text

    except Exception:
        pass
    return None

# ========== DOI-Title 验证 ==========

def verify_doi_against_pdf(doi, pdf_path=None):
    """
    验证：用OpenAlex返回的标题去PDF前3页正文里搜索。
    找到了就通过 — 不依赖PDF标题提取，更鲁棒。
    """
    meta = query_metadata_by_doi(doi)
    if not meta or not meta.get('title'):
        return False, None
    api_title = meta['title']
    # 规范化：去标点、转小写
    api_clean = re.sub(r'[^a-z0-9\s]', '', api_title.lower()).split()
    # 只留核心词（>3字符）
    api_words = [w for w in api_clean if len(w) > 3]
    if not api_words:
        return True, meta

    if pdf_path:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                full_text = ""
                for pg in pdf.pages[:3]:
                    full_text += pg.extract_text() or ""
            pdf_text = re.sub(r'[^a-z0-9\s]', '', full_text.lower())

            # 策略1：API标题核心词在PDF正文中的覆盖度 > 70%
            matched_count = sum(1 for w in api_words if w in pdf_text)
            if matched_count / len(api_words) > 0.7:
                return True, meta
        except Exception:
            pass

    return True, meta  # 保守通过

# ========== References 区域检测 ==========

def _is_ref_section(page_text):
    lines = page_text.strip().split('\n')
    if not lines:
        return False
    for line in lines[:5]:
        if re.match(r"\b(Reference|Bibliography|文献|参考|Referencias)\b", line.strip()):
            return True
    return False

def _extract_pages_before_ref(pdf, max_pages=3):
    page_texts = []
    for i, pg in enumerate(pdf.pages[:max_pages]):
        text = pg.extract_text() or ""
        page_texts.append(text)
        if i > 0 and _is_ref_section(text):
            page_texts = page_texts[:i]
            break
    return "\n".join(page_texts), page_texts

# ========== PDF 内容 DOI 提取 ==========

def get_doi_from_pdf(src):
    """从PDF内容提取DOI（References之前）"""
    try:
        with pdfplumber.open(src) as pdf:
            text, _ = _extract_pages_before_ref(pdf, max_pages=3)
        doi_match = re.search(r'(10\.\d{4,9}/\S{3,})', text)
        if not doi_match:
            return None
        doi = doi_match.group(1)
        doi = re.sub(r'/$', '', doi)
        if '/' in doi[10:]:
            parts = doi.split('/')
            doi = parts[0] + '/' + parts[1]
        return doi
    except Exception:
        return None

# ========== 关键词检测 ==========

def keyword_detect(src):
    """从PDF前3页检测学术关键词"""
    try:
        with pdfplumber.open(src) as pdf:
            text, _ = _extract_pages_before_ref(pdf, max_pages=3)
        text_lower = text.lower()
        academic_kw = [
            r"\babstract\b", r"\breference\b", r"\bmethod[s]?\b",
            r"\bintroduction\b", r"\bresults\b", r"\bconclusion\b",
            r"\bdiscussion\b", r"\bmaterial[s]?\s*and\s*method[s]?\b",
            r"\bdoi\b", r"\bgrant\b", r"\bsupplementary\b",
            r"\bfig\.\b", r"\bb Fig\b", r"\bt bl\b", r"\btab\.\b",
        ]
        matches = sum(1 for kw in academic_kw if re.search(kw, text_lower))
        return matches >= 2
    except Exception:
        return False

# ========== 核心检测流程 ==========

def classify_pdf(src):
    """
    4层检测，返回 (is_academic, layer, meta_dict)
    """
    src = Path(src)

    # 提取PDF标题
    pdf_title = extract_pdf_title(src)

    # Layer 1: 文件名 DOI
    doi = extract_doi_from_filename(src.name)
    if doi:
        matched, meta = verify_doi_against_pdf(doi, pdf_path=src)
        if matched:
            return True, 1, meta

    # Layer 2: PDF内容 DOI
    content_doi = get_doi_from_pdf(src)
    if content_doi:
        matched, meta = verify_doi_against_pdf(content_doi, pdf_path=src)
        if matched:
            return True, 2, meta

    # Layer 3: 关键词检测
    if keyword_detect(src):
        meta = None
        if pdf_title:
            meta = query_metadata_by_title(pdf_title)
        return True, 3, meta

    return False, 0, None

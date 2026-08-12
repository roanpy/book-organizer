# -*- coding: utf-8 -*-
"""
元数据模块 - 处理图书元数据的提取和写入

包含：
- PDF/EPUB 元数据提取
- XMP 元数据处理（Calibre 兼容）
- 元数据写入
"""

import os
import shutil
import uuid
import zipfile
from typing import Any, Dict, Set, Tuple

# 可选库导入
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import ebooklib
    from ebooklib import epub
except ImportError:
    ebooklib = None
    epub = None


def _extract_pdf_xmp_metadata(doc: Any) -> Tuple[Dict[str, Any], bool]:
    """从 PDF 的 XMP 元数据中提取 Calibre 格式的标签和丛书信息。

    Args:
        doc: PyMuPDF 文档对象

    Returns:
        tuple: (metadata_dict, has_xmp)
    """
    metadata: Dict[str, Any] = {}
    has_xmp = False

    try:
        from defusedxml import ElementTree as ET

        xmp = doc.get_xml_metadata()
        if not xmp:
            return metadata, False

        has_xmp = True
        root = ET.fromstring(xmp)

        namespaces = {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "dc": "http://purl.org/dc/elements/1.1/",
            "calibre": "http://calibre.kovidgoyal.net/2009/metadata",
        }

        for desc in root.findall(".//rdf:Description", namespaces):
            # 标签
            tags = []
            for container in ["Bag", "Seq", "Alt"]:
                subjects = desc.findall(
                    f".//dc:subject/rdf:{container}/rdf:li", namespaces
                )
                if subjects:
                    tags.extend(
                        [s.text.strip() for s in subjects if s.text and s.text.strip()]
                    )

            if not tags:
                subject = desc.find(".//dc:subject", namespaces)
                if subject is not None and subject.text:
                    tags.append(subject.text.strip())

            if tags:
                seen: Set[str] = set()
                unique_tags = []
                for x in tags:
                    if x not in seen:
                        seen.add(x)
                        unique_tags.append(x)
                metadata["tags"] = ", ".join(unique_tags)

            # 丛书
            series = None
            series_elem = desc.find(".//calibre:series", namespaces)
            if series_elem is not None and series_elem.text:
                series = series_elem.text.strip()

            if not series:
                series = desc.get(f"{{{namespaces['calibre']}}}series")

            if series:
                metadata["series"] = series

            # 出版社
            for container in ["Bag", "Seq", "Alt"]:
                publishers = desc.findall(
                    f".//dc:publisher/rdf:{container}/rdf:li", namespaces
                )
                if publishers:
                    for pub in publishers:
                        if pub.text and pub.text.strip():
                            pub_text = pub.text.strip()
                            if not pub_text.startswith("calibre"):
                                metadata["publisher"] = pub_text
                                break

            if "publisher" not in metadata:
                publisher = desc.find(".//dc:publisher", namespaces)
                if publisher is not None and publisher.text:
                    pub_text = publisher.text.strip()
                    if not pub_text.startswith("calibre"):
                        metadata["publisher"] = pub_text

            # 标题
            title_bag = desc.findall(".//dc:title/rdf:Alt/rdf:li", namespaces)
            if title_bag and title_bag[0].text:
                metadata["title"] = title_bag[0].text.strip()

            # 作者
            creator_bag = desc.findall(".//dc:creator/rdf:Seq/rdf:li", namespaces)
            if creator_bag and creator_bag[0].text:
                metadata["author"] = creator_bag[0].text.strip()

    except Exception:
        pass

    return metadata, has_xmp


def validate_epub_format(file_path: str) -> Tuple[bool, str]:
    """验证 EPUB 文件格式完整性。

    ✅ 稳定方法：自 v0.4.3 创建以来未经修改，ZIP/ebooklib 双重验证逻辑可靠。

    Args:
        file_path: EPUB 文件路径

    Returns:
        (is_valid, error_message): 验证结果和错误信息
    """
    try:
        # 1. 检查 ZIP 结构完整性
        with zipfile.ZipFile(file_path, "r") as zf:
            # 检查必需文件
            namelist = zf.namelist()
            if "mimetype" not in namelist:
                return False, "缺少 mimetype 文件"

            # 检查 META-INF/container.xml
            if "META-INF/container.xml" not in namelist:
                return False, "缺少 container.xml"

            # 测试 ZIP 完整性（检查 CRC）
            bad_file = zf.testzip()
            if bad_file:
                return False, f"文件损坏: {bad_file}"

        # 2. 尝试用 ebooklib 读取
        if ebooklib:
            try:
                book = epub.read_epub(file_path)
                # 尝试获取基本信息确认可读
                _ = book.get_metadata("DC", "title")
            except Exception as e:
                return False, f"ebooklib 读取失败: {str(e)}"

        return True, ""
    except zipfile.BadZipFile as e:
        return False, f"ZIP 格式损坏: {str(e)}"
    except Exception as e:
        return False, f"验证失败: {str(e)}"


def validate_pdf_format(file_path: str) -> Tuple[bool, str]:
    """验证 PDF 文件格式完整性。

    ✅ 稳定方法：自 v0.4.3 创建以来未经修改，基于 pikepdf 的简洁验证。

    Args:
        file_path: PDF 文件路径

    Returns:
        (is_valid, error_message): 验证结果和错误信息
    """
    try:
        import pikepdf

        with pikepdf.open(file_path) as pdf:
            # 尝试获取页数确认可读
            _ = len(pdf.pages)
        return True, ""
    except Exception as e:
        return False, f"PDF 验证失败: {str(e)}"


def extract_metadata(file_path: str) -> Dict[str, Any]:
    """从 PDF 和 EPUB 文件中提取元数据。

    ✅ 稳定方法：自 v0.3.23 创建以来仅作小幅优化，核心提取逻辑充分验证。

    Args:
        file_path: 文件路径

    Returns:
        包含元数据的字典（title, author, publisher, tags, series 等）
    """
    metadata = {}
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            try:
                import fitz

                doc = fitz.open(file_path)

                # 从 XMP 元数据读取
                xmp_metadata, has_xmp = _extract_pdf_xmp_metadata(doc)
                if xmp_metadata:
                    metadata.update(xmp_metadata)

                # 从标准 PDF 元数据补充
                pdf_meta = doc.metadata

                if not metadata.get("title") and pdf_meta.get("title"):
                    metadata["title"] = pdf_meta["title"]
                if not metadata.get("author") and pdf_meta.get("author"):
                    metadata["author"] = pdf_meta["author"]

                if not metadata.get("publisher"):
                    if pdf_meta.get("creator"):
                        creator = pdf_meta["creator"]
                        if not creator.startswith("calibre"):
                            metadata["publisher"] = creator

                if not metadata.get("tags"):
                    if pdf_meta.get("subject"):
                        metadata["tags"] = pdf_meta["subject"]
                    elif pdf_meta.get("keywords"):
                        keywords = pdf_meta["keywords"]
                        tags_from_keywords = []
                        keyword_parts = [k.strip() for k in keywords.split(",")]
                        for part in keyword_parts:
                            if part.startswith("丛书:"):
                                series_name = part.replace("丛书:", "").strip()
                                if (
                                    series_name
                                    and not has_xmp
                                    and "series" not in metadata
                                ):
                                    metadata["series"] = series_name
                            elif part:
                                tags_from_keywords.append(part)

                        if tags_from_keywords:
                            metadata["tags"] = ", ".join(tags_from_keywords)

                doc.close()
            except ImportError:
                if PdfReader:
                    with open(file_path, "rb") as f:
                        reader = PdfReader(f)
                        info = reader.metadata
                        if info:
                            if info.title:
                                metadata["title"] = info.title
                            if info.author:
                                metadata["author"] = info.author

        elif ext == ".epub" and ebooklib:
            book = epub.read_epub(file_path)

            titles = book.get_metadata("DC", "title")
            if titles and len(titles) > 0 and len(titles[0]) > 0:
                metadata["title"] = titles[0][0]

            authors = book.get_metadata("DC", "creator")
            if authors and len(authors) > 0 and len(authors[0]) > 0:
                metadata["author"] = authors[0][0]

            publishers = book.get_metadata("DC", "publisher")
            if publishers and len(publishers) > 0 and len(publishers[0]) > 0:
                metadata["publisher"] = publishers[0][0]

            descriptions = book.get_metadata("DC", "description")
            if descriptions and len(descriptions) > 0 and len(descriptions[0]) > 0:
                metadata["description"] = descriptions[0][0]

            subjects = book.get_metadata("DC", "subject")
            if subjects:
                tags_list = [
                    subj[0] for subj in subjects if subj and len(subj) > 0 and subj[0]
                ]
                if tags_list:
                    metadata["tags"] = ", ".join(tags_list)

            # 丛书 (Calibre series)
            opf_ns = "http://www.idpf.org/2007/opf"
            if opf_ns in book.metadata:
                meta_items = book.metadata[opf_ns].get("meta", [])
                for meta_item in meta_items:
                    if len(meta_item) >= 2 and isinstance(meta_item[1], dict):
                        attrs = meta_item[1]
                        if attrs.get("name") == "calibre:series":
                            series_name = attrs.get("content")
                            if series_name:
                                metadata["series"] = series_name
                                break

    except Exception as e:
        print(f"  ⚠️ 读取元数据失败 [{os.path.basename(file_path)}]: {e}")

    return metadata


def write_epub_metadata(file_path: str, metadata: Dict[str, Any]) -> bool:
    """更新 EPUB 文件的内部元数据（直接修改 OPF，不重写整个文件）。

    ⚠️ 稳定性警告：此函数经过充分验证，请勿随意修改！

    实现原理：
    1. 使用 zipfile + lxml 直接修改 OPF 文件中的 metadata
    2. 不使用 ebooklib 写入，避免 spine/toc 被修改
    3. 写入后自动验证格式完整性，失败则从备份恢复

    支持的字段：title, creator(author), publisher, subject(tags),
                 calibre:series, description

    Args:
        file_path: EPUB 文件路径
        metadata: 元数据字典

    Returns:
        bool: 是否成功更新
    """
    if not os.path.exists(file_path):
        return False

    ext = os.path.splitext(file_path)[1].lower()
    if ext != ".epub":
        return False

    backup_path = file_path + f".backup.{uuid.uuid4().hex}"
    try:
        shutil.copy2(file_path, backup_path)
    except Exception as e:
        print(f"  ⚠️ 无法创建备份文件: {e}")
        return False

    try:
        import tempfile

        from lxml import etree

        # 定义命名空间
        DC_NS = "http://purl.org/dc/elements/1.1/"
        OPF_NS = "http://www.idpf.org/2007/opf"
        OPF_NS = "http://www.idpf.org/2007/opf"

        # 找到 OPF 文件路径
        opf_path = None
        with zipfile.ZipFile(file_path, "r") as zf:
            # 从 container.xml 获取 OPF 路径
            try:
                container = etree.fromstring(zf.read("META-INF/container.xml"))
                rootfile = container.find(
                    ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
                )
                if rootfile is not None:
                    opf_path = rootfile.get("full-path")
            except Exception:
                pass

            # 尝试常见路径
            if not opf_path:
                for path in ["content.opf", "OEBPS/content.opf", "EPUB/content.opf"]:
                    if path in zf.namelist():
                        opf_path = path
                        break

            if not opf_path:
                raise Exception("找不到 OPF 文件")

            # 读取 OPF 内容
            opf_content = zf.read(opf_path)

        # 解析 OPF
        opf_tree = etree.fromstring(opf_content)
        metadata_elem = opf_tree.find(".//{%s}metadata" % OPF_NS)
        if metadata_elem is None:
            metadata_elem = opf_tree.find(".//metadata")

        if metadata_elem is None:
            raise Exception("找不到 metadata 元素")

        # 辅助函数：更新或添加 DC 元素
        def update_dc_element(tag, value):
            elem = metadata_elem.find(f"{{{DC_NS}}}{tag}")
            if elem is not None:
                elem.text = value
            else:
                new_elem = etree.SubElement(metadata_elem, f"{{{DC_NS}}}{tag}")
                new_elem.text = value

        # 更新元数据
        if metadata.get("title"):
            update_dc_element("title", metadata["title"])

        if metadata.get("author"):
            update_dc_element("creator", metadata["author"])

        if metadata.get("publisher"):
            update_dc_element("publisher", metadata["publisher"])

        # 标签 (subjects)
        if metadata.get("tags"):
            # 移除现有 subjects
            for elem in metadata_elem.findall(f"{{{DC_NS}}}subject"):
                metadata_elem.remove(elem)
            # 添加新 subjects
            tags_str = metadata["tags"]
            if isinstance(tags_str, str):
                tags_list = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
                for tag in tags_list:
                    new_elem = etree.SubElement(metadata_elem, f"{{{DC_NS}}}subject")
                    new_elem.text = tag

        # 丛书 (calibre:series)
        if metadata.get("series"):
            # 移除现有 calibre:series
            for meta in metadata_elem.findall(f"{{{OPF_NS}}}meta"):
                if meta.get("name") == "calibre:series":
                    metadata_elem.remove(meta)
            for meta in metadata_elem.findall("meta"):
                if meta.get("name") == "calibre:series":
                    metadata_elem.remove(meta)
            # 添加新的
            new_meta = etree.SubElement(metadata_elem, "meta")
            new_meta.set("name", "calibre:series")
            new_meta.set("content", metadata["series"])

        # 增强简介 (description) - 直接替换，不追加
        if metadata.get("description"):
            new_summary = metadata["description"]

            # 获取现有 description 元素
            desc_elem = metadata_elem.find(f"{{{DC_NS}}}description")

            if desc_elem is not None:
                desc_elem.text = new_summary
            else:
                new_elem = etree.SubElement(metadata_elem, f"{{{DC_NS}}}description")
                new_elem.text = new_summary

        # 序列化修改后的 OPF
        new_opf_content = etree.tostring(
            opf_tree, encoding="utf-8", xml_declaration=True
        )

        # 创建临时文件并更新 ZIP
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
            tmp_path = tmp_file.name

        with zipfile.ZipFile(file_path, "r") as zf_in:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
                for item in zf_in.infolist():
                    if item.filename == opf_path:
                        # 写入修改后的 OPF
                        zf_out.writestr(item, new_opf_content)
                    elif item.filename == "mimetype":
                        # mimetype 必须无压缩且在最前
                        zf_out.writestr(
                            item,
                            zf_in.read(item.filename),
                            compress_type=zipfile.ZIP_STORED,
                        )
                    else:
                        # 复制其他文件
                        zf_out.writestr(item, zf_in.read(item.filename))

        # 替换原文件
        shutil.move(tmp_path, file_path)

        # 格式完整性验证
        is_valid, error_msg = validate_epub_format(file_path)
        if not is_valid:
            raise Exception(f"格式验证失败: {error_msg}")

        os.remove(backup_path)
        print("  ✓ EPUB 元数据写入成功并通过格式验证")
        return True

    except Exception as e:
        print(f"  ⚠️ 更新 EPUB 元数据失败: {e}")
        try:
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                os.remove(backup_path)
                print("  ✓ 已从备份恢复原始文件")
        except Exception:
            pass
        return False


def write_pdf_metadata(file_path: str, metadata: Dict[str, Any]) -> bool:
    """更新 PDF 文件的内部元数据。

    Args:
        file_path: PDF 文件路径
        metadata: 元数据字典

    Returns:
        bool: 是否成功更新
    """
    if not os.path.exists(file_path):
        return False

    ext = os.path.splitext(file_path)[1].lower()
    if ext != ".pdf":
        return False

    backup_path = file_path + f".backup.{uuid.uuid4().hex}"
    try:
        shutil.copy2(file_path, backup_path)
    except Exception as e:
        print(f"  ⚠️ 无法创建备份文件: {e}")
        return False

    try:
        import pikepdf

        with pikepdf.open(file_path, allow_overwriting_input=True) as pdf:
            with pdf.open_metadata(
                set_pikepdf_as_editor=False, update_docinfo=True
            ) as xmp:
                if "title" in metadata and metadata.get("title"):
                    xmp["dc:title"] = metadata["title"]

                if "author" in metadata and metadata.get("author"):
                    xmp["dc:creator"] = [metadata["author"]]

                if "publisher" in metadata and metadata.get("publisher"):
                    xmp["dc:publisher"] = [metadata["publisher"]]

                if "tags" in metadata:
                    tags_str = metadata.get("tags", "").strip()
                    if tags_str:
                        tags_list = [
                            tag.strip() for tag in tags_str.split(",") if tag.strip()
                        ]
                        if tags_list:
                            xmp["dc:subject"] = tags_list
                        elif "dc:subject" in xmp:
                            del xmp["dc:subject"]
                    elif "dc:subject" in xmp:
                        del xmp["dc:subject"]

                if "series" in metadata:
                    series_str = metadata.get("series", "").strip()
                    if series_str:
                        xmp["calibre:series"] = series_str
                    elif "calibre:series" in xmp:
                        del xmp["calibre:series"]

                if "description" in metadata and metadata.get("description"):
                    new_summary = metadata["description"]
                    separator = "\n\n★ 增强简介 (AI Generated) ★\n"

                    current_desc = ""
                    if "dc:description" in xmp:
                        current_desc = str(xmp["dc:description"])

                    final_desc = new_summary
                    if current_desc:
                        if separator in current_desc:
                            parts = current_desc.split(separator)
                            final_desc = parts[0] + separator + new_summary
                        elif new_summary not in current_desc:
                            final_desc = current_desc + separator + new_summary
                    else:
                        final_desc = separator + new_summary

                    xmp["dc:description"] = final_desc

            pdf.save()

        # 基本大小检查
        if os.path.getsize(file_path) < 1000:
            raise Exception("写入后文件大小异常")

        # 格式完整性验证
        is_valid, error_msg = validate_pdf_format(file_path)
        if not is_valid:
            raise Exception(f"格式验证失败: {error_msg}")

        os.remove(backup_path)
        print("  ✓ PDF 元数据写入成功并通过格式验证")
        return True

    except Exception as e:
        print(f"  ⚠️ 更新 PDF 元数据失败: {e}")
        try:
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                os.remove(backup_path)
                print("  ✓ 已从备份恢复原始文件")
        except Exception:
            pass
        return False

from book_organizer import metadata


class _UnsafeXmpDocument:
    def get_xml_metadata(self):
        return """<?xml version="1.0"?>
        <!DOCTYPE x [<!ENTITY external SYSTEM "file:///etc/passwd">]>
        <x>&external;</x>"""


def test_pdf_xmp_rejects_external_entities():
    parsed, has_xmp = metadata._extract_pdf_xmp_metadata(_UnsafeXmpDocument())

    assert has_xmp is True
    assert parsed == {}

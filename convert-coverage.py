"""Convert a cov.xml report so that it is usable locally"""
import os.path

from lxml import etree as et  # type: ignore

cov = et.parse("cov.xml")

[source] = et.XPath("//source")(cov)

source.text = os.path.abspath("tarts")

with open("cov.xml", "wb") as f:
    f.write(et.tostring(cov, xml_declaration=True))

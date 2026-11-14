"""Project an already-obtained official team-roster HTML response; no network.

Input pages remain temporary. This helper emits factual name, jersey, position,
section and player-link fields only; it does not establish game-active status.
"""
from html.parser import HTMLParser
import re


class RosterParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = self.cell = self.row = self.heading = None
        self.heading_text = []
        self.last_heading = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if re.fullmatch(r"h[2-5]", tag) and self.table is None:
            self.heading, self.heading_text = tag, []
        if tag == "table":
            self.table = {"section": self.last_heading, "headers": [], "rawrows": []}
            self.tables.append(self.table)
        if self.table is not None:
            if tag == "tr":
                self.row = []
            if tag in ("td", "th", "caption"):
                self.cell = {"kind": tag, "text": [], "links": []}
            if tag == "a" and self.cell is not None:
                self.cell["links"].append(attrs.get("href"))

    def handle_data(self, data):
        if self.heading:
            self.heading_text.append(data)
        if self.cell is not None:
            self.cell["text"].append(data)

    def handle_endtag(self, tag):
        if tag == self.heading:
            self.last_heading = " ".join(" ".join(self.heading_text).split())
            self.heading = None
        if self.table is not None:
            if self.cell is not None and tag == self.cell["kind"]:
                self.cell["value"] = " ".join(" ".join(self.cell.pop("text")).split())
                if tag == "caption":
                    self.table["section"] = self.cell["value"]
                elif tag == "th":
                    self.table["headers"].append(self.cell["value"])
                elif self.row is not None:
                    self.row.append(self.cell)
                self.cell = None
            if tag == "tr" and self.row:
                self.table["rawrows"].append(self.row)
                self.row = None
            if tag == "table":
                self.table = None


def extract(html, team):
    parser = RosterParser()
    parser.feed(html)
    rows, tables = [], []
    for index, table in enumerate(parser.tables):
        data = []
        for raw in table["rawrows"]:
            if len(raw) < 3:
                continue
            item = {
                "team": team,
                "source_section": table["section"],
                "name": raw[0]["value"],
                "jersey": raw[1]["value"],
                "position": raw[2]["value"],
                "team_player_url": raw[0]["links"][0] if raw[0]["links"] else None,
            }
            data.append(item)
            rows.append(item)
        tables.append({"index": index, "section": table["section"],
                       "headers": table["headers"], "rows": len(data)})
    return tables, rows

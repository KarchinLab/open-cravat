import sqlite3
import unittest

from cravat.cravat_filter import FilterColumn, FilterGroup


class TestFilterColumnSql(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE variant ("
            "base__chrom TEXT, base__pos INT, base__so TEXT, tagsampler__samples TEXT)"
        )
        self.conn.executemany(
            "INSERT INTO variant VALUES (?, ?, ?, ?)",
            [
                ("chr1", 100, "MIS", "s1;s2"),
                ("chr2", 200, "SYN", "s2;s3"),
                ("chr3", 300, "MIS", "s3"),
            ],
        )

    def tearDown(self):
        self.conn.close()

    def _query(self, where_sql):
        return self.conn.execute(
            f"SELECT base__chrom FROM variant WHERE {where_sql} ORDER BY base__pos"
        ).fetchall()

    def test_between_sql_is_valid_sqlite(self):
        col = FilterColumn({"column": "base__pos", "test": "between", "value": [50, 250]}, "and")
        self.assertEqual([("chr1",), ("chr2",)], self._query(col.get_sql()))

        neg = FilterColumn(
            {"column": "base__pos", "test": "between", "value": [50, 250], "negate": True},
            "and",
        )
        self.assertEqual([("chr3",)], self._query(neg.get_sql()))

    def test_equals_list_matches_all_values(self):
        str_col = FilterColumn(
            {"column": "base__chrom", "test": "equals", "value": ["chr1", "chr2"]},
            "and",
        )
        self.assertEqual([("chr1",), ("chr2",)], self._query(str_col.get_sql()))

        int_col = FilterColumn(
            {"column": "base__pos", "test": "equals", "value": [100, 300]},
            "and",
        )
        self.assertEqual([("chr1",), ("chr3",)], self._query(int_col.get_sql()))

        group = FilterGroup(
            {
                "operator": "and",
                "rules": [
                    {"column": "base__so", "test": "equals", "value": "MIS"},
                    {"column": "base__chrom", "test": "equals", "value": ["chr1", "chr2"]},
                ],
            }
        )
        self.assertEqual([("chr1",)], self._query(group.get_sql()))

    def test_multicategory_respects_and_group_precedence(self):
        group = FilterGroup(
            {
                "operator": "and",
                "rules": [
                    {"column": "base__so", "test": "equals", "value": "MIS"},
                    {"column": "tagsampler__samples", "test": "multicategory", "value": ["s1", "s3"]},
                ],
            }
        )
        self.assertEqual([("chr1",), ("chr3",)], self._query(group.get_sql()))


if __name__ == "__main__":
    unittest.main()

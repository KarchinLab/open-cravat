import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from cravat.base_mapper import BaseMapper


class TestBaseMapper(unittest.TestCase):
    def test_run_as_slave_writes_unmapped_variant_after_exception(self):
        mapper = BaseMapper.__new__(BaseMapper)
        records = [
            (1, "record 1", {"uid": 1, "alt_base": "G"}),
            (2, "record 2", {"uid": 2, "alt_base": "T"}),
            (3, "record 3", {"uid": 3, "alt_base": "C"}),
        ]
        mapper.reader = MagicMock()
        mapper.reader.loop_data.return_value = iter(records)
        mapper.crx_writer = MagicMock()
        mapper.status_writer = None
        mapper.args = SimpleNamespace(seekpos=0)
        mapper.conf = {"title": "Test mapper"}
        mapper.module_name = "test_mapper"
        mapper.logger = MagicMock()
        mapper.base_setup = MagicMock()
        mapper._add_crx_to_gene_info = MagicMock()
        mapper._write_crg = MagicMock()
        mapper._log_runtime_error = MagicMock()
        mapper.end = MagicMock()

        def map_record(crv_data):
            if crv_data["uid"] == 2:
                raise ValueError("mapping failed")
            return {**crv_data, "all_mappings": "{}"}

        mapper.map = map_record

        mapper.run_as_slave(0)

        output_records = [
            call.args[0] for call in mapper.crx_writer.write_data.call_args_list
        ]
        output_uids = [record["uid"] for record in output_records]
        self.assertEqual([1, 2, 3], output_uids)
        self.assertEqual(len(output_uids), len(set(output_uids)))
        self.assertEqual("{}", output_records[1]["all_mappings"])
        mapper._log_runtime_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()

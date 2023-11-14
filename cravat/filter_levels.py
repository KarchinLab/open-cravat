from collections import namedtuple

# A named tuple that contains the attributes of a filter that change frequently based on level
LevelConfig = namedtuple("LevelConfig", "base_table filter_table key")

VariantLevel = LevelConfig(
    base_table="variant",
    filter_table="variant_filtered",
    key="base__uid"
)

SampleLevel = LevelConfig(
    base_table="sample",
    filter_table="variant_filtered",
    key="base__uid"
)

MappingLevel = LevelConfig(
    base_table="mapping",
    filter_table="variant_filtered",
    key="base__uid"
)

class FilterQuery:
    # The base set of queries, join the level table to the appropriate filter table using the configured key

    def __init__(self, level_config):
        self.level_config = level_config

    @property
    def filtered_sql(self):
        return """
            select v.*
            from {base_table} as v
            inner join {filter_table} as f on v.{key} == f.{key}
        """.format(**self.level_config._asdict())

    @property
    def unfiltered_sql(self):
        return """
            select v.*
            from {base_table} as v
        """.format(**self.level_config._asdict())


class GeneQuery(FilterQuery):
    # Queries for gene level data, use the gene table as base, but join based on hugo and variant
    def __init__(self):
        super().__init__(LevelConfig(
            base_table="gene",
            filter_table="gene_filtered",
            key="base__hugo"
        ))

    @property
    def unfiltered_sql(self):
        return """
            select distinct gene.*
            from variant
            inner join gene on variant.base__hugo = gene.base__hugo
        """


LevelQueries = {
    'mapping': FilterQuery(MappingLevel),
    'variant': FilterQuery(VariantLevel),
    'sample': FilterQuery(SampleLevel),
    'gene': GeneQuery()
}
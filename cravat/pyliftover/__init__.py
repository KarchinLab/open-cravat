'''
Pure-python implementation of UCSC "liftover" genome coordinate conversion.

Copyright 2013, Konstantin Tretyakov.
http://kt.era.ee/

Licensed under MIT license.

PyLiftover is a library for quick and easy conversion of genomic (point) coordinates between different assemblies.

It uses the same logic and coordinate conversion mappings as the UCSC `liftOver tool<http://genome.ucsc.edu/cgi-bin/hgLiftOver>`_.

The primary usage example, supported by the library is the following::

    >> from pyliftover import LiftOver
    >> lo = LiftOver('hg17', 'hg18')
    >> lo.convert_coordinate('chr1', 1000000)

The first line will automatically download the hg17-to-hg18 coordinate conversion `chain file<http://genome.ucsc.edu/goldenPath/help/chain.html>` from UCSC,
unless it is already cached or available in the current directory. Alternatively, you may provide your own chain file::

    >> lo = LiftOver('hg17ToHg18.over.chain.gz')
    >> lo.convert_coordinate('chr1', 1000000, '-')

The result of ``lo.convert_coordinate`` call is either ``None`` (if the source chromosome name is unrecognized) or a list of target positions in the
new assembly. The list may be empty (locus is deleted in the new assembly), have a single element (locus matched uniquely), or, in principle, 
have multiple elements (although this is probably a rare occasion for most default intra-species genomic conversions).

Although you may try to apply the tool with arbitrary chain files, like the original ``liftOver`` tool, it makes most sense for conversion of 
coordinates between different assemblies of the same species.
'''
__version__ = "0.4"

from .liftover import LiftOver
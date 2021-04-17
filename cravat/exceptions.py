class InvalidData(Exception):
    notraceback = True
    pass


class ConfigurationError(Exception):
    pass


class BadFormatError(InvalidData):
    pass


class LiftoverFailure(InvalidData):
    pass


class FileIntegrityError(Exception):
    def __init__(self, path):
        super().__init__(path)


class CravatProfileException:
    def __init__(self, msg):
        super().__init__(msg)


class ExpectedException(Exception):
    pass


class KillInstallException(Exception):
    pass


class InvalidReporter(Exception):
    pass


class NoVariantError(Exception):
    def __init__(self):
        super().__init__("Reference and alternate alleles are the same.")

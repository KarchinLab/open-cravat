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


class InvalidModule(Exception):
    def __init__(self, module_name):
        self.msg = "Invalid module: {}".format(module_name)

    def __str__(self):
        return self.msg


class NoVariantError(Exception):
    def __init__(self):
        super().__init__("Reference and alternate alleles are the same.")

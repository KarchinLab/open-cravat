class InvalidData(Exception):
    pass

class ConfigurationError(Exception):
    pass

class BadFormatError(InvalidData):
    pass

class LiftoverFailure(InvalidData):
    def __init__(self,chrom,pos):
        msg = '%s:%s' %(chrom,str(pos))
        super().__init__(msg)
        
class FileIntegrityError(Exception):
    def __init__(self, path):
        super().__init__(path)
        
class CravatProfileException():
    def __init__(self, msg):
        super().__init__(msg)

class ExpectedException (Exception):
    pass

class KillInstallException (Exception):
    pass

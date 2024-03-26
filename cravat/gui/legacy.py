# this module is to wrap code from the legacy web codebase
# ideally anything imported or declared here should be replaced

# Re-exports
from cravat.websubmit import websubmit

FileRouter = websubmit.FileRouter
def get_job():
    websubmit.get_job()


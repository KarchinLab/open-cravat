class BaseCommonModule(object):
    def __init__(self):
        pass

    def _log_exception(self, e, halt=True):
        if halt:
            raise e
        else:
            if self.logger:
                self.logger.exception(e)

    def _define_cmd_parser(self):
        try:
            parser = argparse.ArgumentParser()
            self.cmd_arg_parser = parser
        except Exception as e:
            self._log_exception(e)

    def parse_cmd_args(self, cmd_args):
        try:
            self._define_cmd_parser()
            parsed_args = self.cmd_arg_parser.parse_args(cmd_args[1:])
        except Exception as e:
            self._log_exception(e)

    def setup(self):
        pass

    def _setup_logger(self):
        try:
            self.logger = logging.getLogger("cravat." + self.module_name)
            if self.output_basename != "__dummy__":
                self.log_path = os.path.join(
                    self.output_dir, self.output_basename + ".log"
                )
                log_handler = logging.FileHandler(self.log_path, "a")
            else:
                log_handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s %(name)-20s %(message)s", "%Y/%m/%d %H:%M:%S"
            )
            log_handler.setFormatter(formatter)
            self.logger.addHandler(log_handler)
            self.error_logger = logging.getLogger("error." + self.module_name)
            if self.output_basename != "__dummy__":
                error_log_path = os.path.join(
                    self.output_dir, self.output_basename + ".err"
                )
                error_log_handler = logging.FileHandler(error_log_path, "a")
            else:
                error_log_handler = logging.StreamHandler()
            formatter = logging.Formatter("SOURCE:%(name)-20s %(message)s")
            error_log_handler.setFormatter(formatter)
            self.error_logger.addHandler(error_log_handler)
        except Exception as e:
            self._log_exception(e)
        self.unique_excs = []

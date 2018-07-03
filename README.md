OpenCRAVAT is a local, modular, and light-weight variant annotation tool.

To install open CRAVAT you need Python 3.5 or newer.

### Installing Core

`pip install cravat`

### Installing Base Components

Then you need some base components. One is big so will take ~15 minutes to install.

`cravat-admin install-base`

### Installing Annotators

Then you can search for annotators to install with the command

`cravat-admin ls –a`

This also tells you wich annotators you have installed.

To install a new one:

`cravat-admin install <annotator name>`

For example: `cravat-admin install clinvar`

Depending on the size of the data for the annotator, it may take some time to download and install.

### Running Analysis

To run your analysis you then can just type:

`cravat <input file>`

This command has lots of command line options you can see by typing cravat –h.  By default, it will create text, excel, and sqlite output in the current directoy and will run all of the installed annotators.  Command line options can be used to select specific output or to run a subset of the installed annotators.

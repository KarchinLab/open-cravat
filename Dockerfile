FROM python:3.11

ARG PACKAGEDIR=/usr/local/lib/python3.11/site-packages/cravat

# Install utilities
RUN apt update && \
	apt install -y vim sqlite3 tabix

# Needed for gds-converter module
# Install latest R, following docs at https://cloud.r-project.org/bin/linux/debian/
RUN apt install -y --no-install-recommends software-properties-common dirmngr && \
    apt-key adv --keyserver keyserver.ubuntu.com --recv-key '95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7' && \
    apt update && apt install -y r-base && \
    pip install rpy2
# Install R packages
RUN R -e 'options(Ncpus = parallel::detectCores()); install.packages("BiocManager"); BiocManager::install("SeqArray");'

# Install oc and python libraries
COPY . /src/open-cravat/
RUN pip install /src/open-cravat && \
	pip install \
		open-cravat-multiuser \
		aiosqlite3 \
		scipy \
		pytabix \
		biopython \
		pandas \
		pyreadr
 
# Run oc version to create some directories, then symlink to /mnt
RUN oc version && \
    mv $PACKAGEDIR/conf    /mnt/conf    && ln -s /mnt/conf    $PACKAGEDIR/conf    && \
    mv $PACKAGEDIR/modules /mnt/modules && ln -s /mnt/modules $PACKAGEDIR/modules && \
    mv $PACKAGEDIR/jobs    /mnt/jobs    && ln -s /mnt/jobs    $PACKAGEDIR/jobs    && \
    mv $PACKAGEDIR/logs    /mnt/logs    && ln -s /mnt/logs    $PACKAGEDIR/logs
VOLUME /mnt/conf
VOLUME /mnt/modules
VOLUME /mnt/jobs
VOLUME /mnt/logs

VOLUME /tmp/job
WORKDIR /tmp/job

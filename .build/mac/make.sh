#!/usr/bin/env bash
# conda should be installed.
# python3.10 environment should be setup.
# Change the variables below as needed.
set -ex

CONDADIR=`realpath ../../miniconda`
ENVNAME=py3
APPDIR=./OpenCRAVAT.app
LAUNCHDIR=./launchers
INSTALL_PATH=$1

if [ -z $INSTALL_PATH ]; then
	echo "What is the path to open-cravat?"
	exit
fi

if ! [ -f $INSTALL_PATH/setup.py ]; then
  echo "$INSTALL_PATH is not a path to a python package root."
  exit
fi

source $CONDADIR/etc/profile.d/conda.sh
conda activate $ENVNAME

pip uninstall open-cravat -y
pip install $INSTALL_PATH

ENVDIR=$CONDADIR/envs/$ENVNAME
RESDIR=$APPDIR/Contents/Resources
rm -rf $RESDIR/bin $RESDIR/conda-meta $RESDIR/include $RESDIR/lib $RESDIR/bin $RESDIR/man $RESDIR/share $RESDIR/ssl
cp -R $ENVDIR/* $RESDIR/
cp -R $LAUNCHDIR $RESDIR/

cp $APPDIR/Contents/Info.plist $RESDIR/Info.plist.bak

plutil -replace CFBundleShortVersionString -string $1 $APPDIR/Contents/Info.plist

cd $RESDIR/bin
sed -i '' -e '1s=^.*python=#!/usr/bin/env python=' -e '1s/$/ -I/' oc

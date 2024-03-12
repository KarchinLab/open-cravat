#!/usr/bin/env bash
set -ex
pkgbuild --root ./OpenCRAVAT.app  --identifier org.karchinlab.open-cravat --scripts Scripts --install-location /Applications/OpenCRAVAT.app OpenCRAVAT.pkgbuild.pkg

title="OpenCRAVAT."
title+=${1}
title+=".pkg"

oldversion=$(find Distribution -exec sed -n 's/<product version="\([^<]*\)"\/>/\1/p' {} +)
newversion=$1
sed -i '' "s@$(echo $oldversion | sed 's/\./\\./g')@$newversion@g" Distribution

productbuild --distribution Distribution --resources Resources ${title}



set -ex



test -e $PREFIX/include/sox.h
test -e $PREFIX/lib/libsox.a
test -e $PREFIX/lib/libsox.so
conda inspect linkages -p $PREFIX $PKG_NAME
sox --help |grep "FILE FORMATS" | grep mp3
exit 0

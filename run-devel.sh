docker run --gpus all --shm-size=32gb --rm -ti -v $PWD:/download_vggsound  -v /raid/home/e3da/datasets/avc/vggsound:/vggsound e3da-vggsound-fpaissan:devel ./train.sh
# docker run --gpus all --shm-size=32gb --rm -ti -v $PWD:/single_bcd  -v /raid/home/e3da/datasets/ucsd:/ucsd e3da-badchanneldetection-fpaissan:devel ./train.sh

FROM nvcr.io/partners/gridai/pytorch-lightning:v1.4.0
COPY requirements.txt ./
RUN pip3 --no-cache-dir install -r requirements.txt
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get -y update
RUN apt-get install -y ffmpeg
WORKDIR /download_vggsound

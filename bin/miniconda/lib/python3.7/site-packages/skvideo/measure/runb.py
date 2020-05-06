import skvideo.measure
import skvideo.io
import skvideo.datasets

prisvid = skvideo.io.vread("/home/luke/databases/video/live_sample/st1_25fps.yuv",
          inputdict={
            "-s": "768x432",
            "-pix_fmt": "yuvj420p",
          },
          as_grey=True
)

disvid = skvideo.io.vread("/home/luke/databases/video/live_sample/st13_25fps.yuv",
          inputdict={
            "-s": "768x432",
            "-pix_fmt": "yuvj420p",
          },
          as_grey=True
)

feat = skvideo.measure.msssim(prisvid, disvid)
print feat

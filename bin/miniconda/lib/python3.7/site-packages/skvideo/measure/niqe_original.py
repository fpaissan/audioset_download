import sys
import BRISQUE
import numpy as np
import glob
import skimage.io
import scipy.misc
from sklearn.externals import joblib
from skimage.util.shape import view_as_windows

import pylab as py

def get_patches_train_features(img, patch_size, stride=8):
    return _get_patches_generic(img, patch_size, 1, stride)

def get_patches_test_features(img, patch_size, stride=8):
    return _get_patches_generic(img, patch_size, 0, stride)

def extract_on_patches(img, patch_size):
    h, w = img.shape
    patches = []
    for j in xrange(0, h-patch_size+1, patch_size):
        for i in xrange(0, w-patch_size+1, patch_size):
            patch = img[j:j+patch_size, i:i+patch_size]
            patches.append(patch)

    patches = np.array(patches)
    
    # patches = view_as_windows(img, (patch_size, patch_size), step=patch_size)
    # patches = patches.reshape(-1, patch_size, patch_size)

    patch_features = []
    for p in patches:
        mscn_features, pp_features = BRISQUE._extract_subband_feats(p)
        patch_features.append(np.hstack((mscn_features, pp_features)))
    patch_features = np.array(patch_features)

    return patch_features

def _get_patches_generic(img, patch_size, is_train, stride):
    h, w = np.shape(img)
    if h < patch_size or w < patch_size:
        print "Input image is too small"
        exit(0)

    # ensure that the patch divides evenly into img
    hoffset = (h % patch_size)
    woffset = (w % patch_size)

    if hoffset > 0: 
        img = img[:-hoffset, :]
    if woffset > 0:
        img = img[:, :-woffset]


    img = img.astype(np.float32)
    #img2 = scipy.misc.imresize(img, 0.5, interp='bicubic', mode='F')
    img2 = scipy.misc.imresize(img, 0.5, interp='bicubic', mode='F')

    #img3 = scipy.misc.imresize(img, 0.25)

    mscn1, var, mu = BRISQUE.calc_image(img)
    mscn1 = mscn1.astype(np.float32)

    mscn2, _, _ = BRISQUE.calc_image(img2)
    mscn2 = mscn2.astype(np.float32)


    feats_lvl1 = extract_on_patches(mscn1, patch_size)
    feats_lvl2 = extract_on_patches(mscn2, patch_size/2)

    # stack the scale features
    feats = np.hstack((feats_lvl1, feats_lvl2))# feats_lvl3))
    # feats = feats_lvl1

    # compute NIQE fast
    if is_train:
        variancefield = view_as_windows(var, (patch_size, patch_size), step=patch_size)
        variancefield = variancefield.reshape(-1, patch_size, patch_size)
        avg_variance = np.mean(np.mean(variancefield, axis=2), axis=1)
        avg_variance /= np.max(avg_variance)

        feats = feats[avg_variance > 0.75]

    return feats

def compute_niqe(img, patch_size, pop_mu, pop_cov):
    # load the training data
    feats = get_patches_test_features(img, patch_size)
    sample_mu = np.mean(feats, axis=0)
    sample_cov = np.cov(feats.T)

    X = sample_mu - pop_mu

    covmat = ((pop_cov+sample_cov)/2.0)

    pinvmat = scipy.linalg.pinv(covmat)
    
    d1 = np.sqrt(np.dot(np.dot(X, pinvmat), X))
    return d1

if __name__ == "__main__":
    patch_size = 96

    # train on the subset of pristine images
    pristine_images = glob.glob("/home/luke/databases/image/BSDS500/*.jpg")

    testing = True
    #testing = False

    if testing:
        # attempt to load mu and covariance computed over a population of pristine images
        pop_mu = joblib.load("niqe_mu_%d.pkl" % (patch_size,))
        pop_cov = joblib.load("niqe_cov_%d.pkl" % (patch_size,))

        # load the challenge database
        matfile_images = np.array(scipy.io.loadmat("/home/luke/databases/image/ChallengeDB_release/Data/AllImages_release.mat")["AllImages_release"]).ravel()
        matfile_scores = np.array(scipy.io.loadmat("/home/luke/databases/image/ChallengeDB_release/Data/AllMOS_release.mat")["AllMOS_release"]).ravel()

        # try NIQE on the pristine set, to check the plumbing
        experimental_data = []
        for idx, (impath, imscore) in enumerate(zip(matfile_images, matfile_scores)):
            impath = "%s/%s" % ("/home/luke/databases/image/ChallengeDB_release/Images", impath[0])
            img = skimage.io.imread(impath)
            img = 0.2989 * img[:, :, 0] + 0.5870 * img[:, :, 1] + 0.1140 * img[:, :, 2]

            # upscaled image
            # img_bad = scipy.misc.imresize(img, 2.0, mode='F')

            distance = compute_niqe(img, patch_size, pop_mu, pop_cov)
            # distance = np.mean(img)

            experimental_data.append([imscore, distance])

            # ideally, distance is close to 0 for the pristine set and far away for the distorted set
            print impath, distance, scipy.stats.spearmanr(np.array(experimental_data)[:, 0], np.array(experimental_data)[:, 1])[0]
    else:

        total_patchbased_features = []
        # grab patches from images
        for idx, impath in enumerate(pristine_images):
            print idx, impath
            img = skimage.io.imread(impath)
            img = 0.2989 * img[:, :, 0] + 0.5870 * img[:, :, 1] + 0.1140 * img[:, :, 2]

            # get the mscn patches from this import image
            feats = get_patches_train_features(img, patch_size)

            if total_patchbased_features == []:
                total_patchbased_features = feats
            else:
                total_patchbased_features = np.vstack((total_patchbased_features, feats))

        total_patchbased_mu = np.mean(total_patchbased_features, axis=0)
        total_patchbased_cov = np.cov(total_patchbased_features.T)

        joblib.dump(total_patchbased_mu, "niqe_mu_%d.pkl" % (patch_size,), compress=9)
        joblib.dump(total_patchbased_cov, "niqe_cov_%d.pkl" % (patch_size,), compress=9)

        print np.shape(total_patchbased_mu)
        print np.shape(total_patchbased_cov)

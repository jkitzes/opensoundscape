#!/usr/bin/env python3
import pandas as pd
import numpy as np
from math import ceil
from hashlib import md5
from sys import stderr
from pathlib import Path
from itertools import chain
import torch
from torchvision import transforms
from PIL import Image, ImageFilter
from time import time

from opensoundscape.audio import Audio
from opensoundscape.spectrogram import Spectrogram
import opensoundscape.torch.tensor_augment as tensaug


def get_md5_digest(input_string):
    """Generate MD5 sum for a string

    Inputs:
        input_string: An input string

    Outputs:
        output: A string containing the md5 hash of input string
    """
    obj = md5()
    obj.update(input_string.encode("utf-8"))
    return obj.hexdigest()


def annotations_with_overlaps_with_clip(df, begin, end):
    """Determine if any rows overlap with current segment

    Inputs:
        df:     A dataframe containing a Raven annotation file
        begin:  The begin time of the current segment (unit: seconds)
        end:    The end time of the current segment (unit: seconds)

    Output:
        sub_df: A dataframe of annotations which overlap with the begin/end times
    """
    return df[
        ((df["begin time (s)"] >= begin) & (df["begin time (s)"] < end))
        | ((df["end time (s)"] > begin) & (df["end time (s)"] <= end))
    ]


class SplitterDataset(torch.utils.data.Dataset):
    """A PyTorch Dataset for splitting a WAV files

    Inputs:
        wavs:                   A list of WAV files to split
        annotations:            Should we search for corresponding annotations files? (default: False)
        label_corrections:      Specify a correction labels CSV file w/ column headers "raw" and "corrected" (default: None)
        overlap:                How much overlap should there be between samples (units: seconds, default: 1)
        duration:               How long should each segment be? (units: seconds, default: 5)
        output_directory        Where should segments be written? (default: segments/)
        include_last_segment:   Do you want to include the last segment? (default: False)
        column_separator:       What character should we use to separate columns (default: "\t")
        species_separator:      What character should we use to separate species (default: "|")

    Effects:
        - Segments will be written to the `output_directory`

    Outputs:
        output: A list of CSV rows (separated by `column_separator`) containing
            the source audio, segment begin time (seconds), segment end time
            (seconds), segment audio, and present classes separated by
            `species_separator` if annotations were requested
    """

    def __init__(
        self,
        wavs,
        annotations=False,
        label_corrections=None,
        overlap=1,
        duration=5,
        output_directory="segments",
        include_last_segment=False,
        column_separator="\t",
        species_separator="|",
    ):
        self.wavs = list(wavs)

        self.annotations = annotations
        self.label_corrections = label_corrections
        if self.label_corrections:
            self.labels_df = pd.read_csv(label_corrections)

        self.overlap = overlap
        self.duration = duration
        self.output_directory = output_directory
        self.include_last_segment = include_last_segment
        self.column_separator = column_separator
        self.species_separator = species_separator

    def __len__(self):
        return len(self.wavs)

    def __getitem__(self, item_idx):
        wav = self.wavs[item_idx]
        annotation_prefix = self.wavs[item_idx].stem.split(".")[0]

        if self.annotations:
            annotation_file = Path(
                f"{wav.parent}/{annotation_prefix}.Table.1.selections.txt.lower"
            )
            if not annotation_file.is_file():
                stderr.write(f"Warning: Found no Raven annotations for {wav}\n")
                return {"data": []}

        audio_obj = Audio.from_file(wav)
        wav_duration = audio_obj.duration()
        wav_times = np.arange(0.0, wav_duration, wav_duration / len(audio_obj.samples))

        if self.annotations:
            annotation_df = pd.read_csv(annotation_file, sep="\t").sort_values(
                by=["begin time (s)"]
            )

        if self.label_corrections:
            annotation_df["class"] = annotation_df["class"].fillna("unknown")
            annotation_df["class"] = annotation_df["class"].apply(
                lambda cls: self.labels_df[self.labels_df["raw"] == cls][
                    "corrected"
                ].values[0]
            )

        num_segments = ceil(
            (wav_duration - self.overlap) / (self.duration - self.overlap)
        )

        outputs = []
        for idx in range(num_segments):
            if idx == num_segments - 1:
                if self.include_last_segment:
                    end = wav_duration
                    begin = end - self.duration
                else:
                    continue
            else:
                begin = self.duration * idx - self.overlap * idx
                end = begin + self.duration

            if self.annotations:
                overlaps = annotations_with_overlaps_with_clip(
                    annotation_df, begin, end
                )

            unique_string = f"{wav}-{begin}-{end}"
            destination = f"{self.output_directory}/{get_md5_digest(unique_string)}"

            if self.annotations:
                if overlaps.shape[0] > 0:
                    segment_sample_begin = audio_obj.time_to_sample(begin)
                    segment_sample_end = audio_obj.time_to_sample(end)
                    audio_to_write = audio_obj.trim(begin, end)
                    audio_to_write.save(f"{destination}.wav")

                    if idx == num_segments - 1:
                        to_append = [
                            wav,
                            annotation_file,
                            wav_times[segment_sample_begin],
                            wav_times[-1],
                            f"{destination}.wav",
                        ]
                    else:
                        to_append = [
                            wav,
                            annotation_file,
                            wav_times[segment_sample_begin],
                            wav_times[segment_sample_end],
                            f"{destination}.wav",
                        ]
                    to_append.append(
                        self.species_separator.join(overlaps["class"].unique())
                    )

                    outputs.append(
                        self.column_separator.join([str(x) for x in to_append])
                    )
            else:
                segment_sample_begin = audio_obj.time_to_sample(begin)
                segment_sample_end = audio_obj.time_to_sample(end)
                audio_to_write = audio_obj.trim(begin, end)
                audio_to_write.save(f"{destination}.wav")

                if idx == num_segments - 1:
                    to_append = [
                        wav,
                        wav_times[segment_sample_begin],
                        wav_times[-1],
                        f"{destination}.wav",
                    ]
                else:
                    to_append = [
                        wav,
                        wav_times[segment_sample_begin],
                        wav_times[segment_sample_end],
                        f"{destination}.wav",
                    ]

                outputs.append(self.column_separator.join([str(x) for x in to_append]))

        return {"data": outputs}

    @classmethod
    def collate_fn(*batch):
        return chain.from_iterable([x["data"] for x in batch[1]])


# class Prototype(torch.utils.data.Dataset):
#     """torch Dataset that can be augmented with additional preprocessing steps
#
#     Given a DataFrame with audio file paths in the index, generate
#     a Dataset of spectrogram tensors for basic machine learning tasks.
#
#     This class provides access to several types of augmentations that act on
#     audio and images with the following arguments:
#     - add_noise: for adding RandomAffine and ColorJitter noise to images
#     - random_trim_length: for only using a short random clip extracted from the training data
#     - max_overlay_num / overlay_prob / overlay_weight:
#         controlling the maximum number of additional spectrograms to overlay,
#         the probability of overlaying an individual spectrogram,
#         and the weight for the weighted sum of the spectrograms
#
#     Additional augmentations on tensors are available when calling `train()`
#     from the module `opensoundscape.torch.train`.
#
#     Input:
#         df: A DataFrame with index containing audio file paths
#             - if labels are provided, they should be "one-hot" encoded
#             - that is, each column is a class and 1=present, 0=absent
#             - a binary classifier would have just one column, for presence
#         from_audio: Whether the raw dataset is audio [default: True]
#         label_column: The column with numeric labels if present [default: None]
#         height: Height for resulting Tensor [default: 224]
#         width: Width for resulting Tensor [default: 224]
#         add_noise: Apply RandomAffine and ColorJitter filters [default: False]
#         save_dir: Save images to a directory [default: None]
#         random_trim_length: Extract a clip of this many seconds of audio
#             starting at a random time. If None, the original clip will be used
#             [default: None]
#         extend_short_clips: If a file to be overlaid or trimmed from is too
#             short, extend it to the desired length by repeating it.
#             [default: False]
#         max_overlay_num: The maximum number of additional images to overlay,
#             each with probability overlay_prob [default: 0]
#         overlay_prob: Probability of an image from a different class being
#             overlayed (combined as a weighted sum)
#             on the training image. typical values: 0, 0.66 [default: 0.2]
#         overlay_weight: The weight given to the overlaid image during
#             augmentation. When 'random', will randomly select a different weight
#             between 0.2 and 0.5 for each overlay. When not 'random', should be a
#             float between 0 and 1 [default: 'random']
#         overlay_class: The label of the class that overlays should be drawn from.
#             Must be specified if max_overlay_num > 0. If 'different', draws
#             overlays from any class that is not the same class as the audio. If
#             set to a class label, draws overlays from that class. When creating
#             a presence/absence classifier, set overlay_class equal to the
#             absence class label [default: None]
#         audio_sample_rate: resample audio to this sample rate; specify None to
#             use original audio sample rate [default: 22050]
#         debug: path to save img files, images are created from the tensor
#             immediately before it is returned. When None, does not save images.
#             [default: None]
#
#     Output:
#         Dictionary:
#             { "X": (3, H, W)
#             , "y": (len(df.columns))
#             }
#     """
#
#     def __init__(
#         self,
#         df,
#         from_audio=True,
#         height=224,
#         width=224,
#         add_noise=False,
#         save_dir=None,
#         random_trim_length=None,
#         extend_short_clips=False,
#         max_overlay_num=0,
#         overlay_prob=0.2,
#         overlay_weight="random",
#         overlay_class=None,
#         tensor_augment=True,
#         audio_sample_rate=22050,
#         debug=None,
#         return_labels=True,
#     ):
#         self.df = df  # TODO: do we want/need to carry this around?
#         self.from_audio = from_audio
#         self.height = height
#         self.width = width
#         self.add_noise = add_noise
#         self.random_trim_length = random_trim_length
#         self.extend_short_clips = extend_short_clips
#         self.max_overlay_num = max_overlay_num
#         self.overlay_prob = overlay_prob
#         self.overlay_weight = overlay_weight
#         self.overlay_class = overlay_class
#         self.tensor_augment = tensor_augment
#         self.audio_sample_rate = audio_sample_rate
#         self.debug = debug
#         self.return_labels = return_labels
#
#         self.labels = self.df.columns
#
#         # Check inputs
#         if (overlay_weight != "random") and (not 0 < overlay_weight < 1):
#             raise ValueError(
#                 f"overlay_weight not in 0<overlay_weight<1 (given overlay_weight: {overlay_weight})"
#             )
#         # if (not self.label_column) and (max_overlay_num != 0):
#         #     raise ValueError(
#         #         "label_column must be specified to use max_overlay_num != 0"
#         #     )
#         if (
#             (self.max_overlay_num > 0)
#             and (self.overlay_class != "different")
#             and (self.overlay_class not in df.columns)
#         ):
#             raise ValueError(
#                 f"overlay_class must either be 'different' or a value of a column header (got overlay_class {self.overlay_class} but labels {df.columns})"
#             )
#
#         # Set up transform, including needed normalization variables
#         self.mean = torch.tensor([0.5 for _ in range(3)])  # [0.8013 for _ in range(3)])
#         self.std_dev = [0.5 for _ in range(3)]  # 0.1576 for _ in range(3)])
#
#         self.pipeline = {
#             self.load_audio: True,
#             self.audio_transform: True,
#             self.audio_to_img: True,
#             self.img_transform: True,
#             self.img_to_tensor: True,
#             self.tensor_transform: True,
#         }
#
#     def load_audio(self, audio_path):
#         """file path in, Audio out"""
#         audio = Audio.from_file(audio_path, sample_rate=self.audio_sample_rate)
#         if len(audio.samples) < 1:
#             raise ValueError(f"loaded audio has got samples from file {audio_path}")
#         # trim to desired length if needed
#         # (if self.random_trim_length is specified, select a clip of that length at random from the original file)
#
#         if self.random_trim_length is not None:
#             # TODO: trimming to constant size deterministically should be default
#             # rather than not trimming at all as default (current)
#             from opensoundscape.preprocess import random_audio_trim
#
#             audio_length = self.random_trim_length
#             audio = random_audio_trim(audio, audio_length, extend_short_clips)
#
#         self.audio_length = audio.duration()
#
#         return audio
#
#     def audio_transform(self, audio):
#         """Audio in, Audio out"""
#         return audio
#
#     def audio_to_img(self, audio):
#         """Audio in, PIL.Image out"""
#         # the reason I think these two should happen in one step
#         # is that it allows other audio to image representations
#         # besides Spectrogram. As long as its Audio->Image it works
#         # -SL
#
#         # convert to spectrogram #maybe this is in audio_to_image?
#         spectrogram = Spectrogram.from_audio(audio)
#
#         # convert to image
#         return spectrogram.to_image(shape=(self.width, self.height), mode="L")
#
#     def img_transform(self, image):
#         """img in, img out"""
#         # transform_list = [transforms.Resize((self.height, self.width))]
#         if self.add_noise:
#             transform_list.extend(
#                 [
#                     transforms.RandomAffine(
#                         degrees=0, translate=(0.2, 0.03), fillcolor=(50, 50, 50)
#                     ),
#                     transforms.ColorJitter(
#                         brightness=0.3, contrast=0.3, saturation=0.3, hue=0
#                     ),
#                 ]
#             )
#         composed_transform = transforms.Compose(transform_list)
#         image = composed_transform(image)
#
#         # overlay other classes. should this happen here?
#         image = self.add_overlays(image)
#
#         # overlayGenerator will be a separate class initialized with .overlay_df
#         # it will recieve x and row_labels, then choose overlay files from
#         # self.overlay_df.
#         # overlay_df is set in Preprocessor() init
#         return image
#
#     def img_to_tensor(self, image):
#         """PIL Image in, torch Tensor out"""
#         image = image.convert("RGB")
#         transform_list = [transforms.ToTensor()]
#         composed_transform = transforms.Compose(transform_list)
#         return composed_transform(image)
#
#     def tensor_transform(self, X):
#         """torch Tensor in, torch Tensor out"""
#         transform_list = [transforms.Normalize(self.mean, self.std_dev)]
#         composed_transform = transforms.Compose(transform_list)
#         X = composed_transform(X)  # returns a tensor!
#
#         # perform tensor augmentations, such as time warp, time mask, and frequency mask
#         if self.tensor_augment:
#             # X is currently shape [3, width, height]
#             # Take to shape [1, 1, width, height] for use with `tensor_augment`
#             # (tensor_augment is design for batch of [1,w,h] tensors)
#             # since batch size is '1' (we are only doing one at a time)
#             X = X[0, :, :].unsqueeze(0).unsqueeze(0)  # was: X = X[:,0].unsqueeze(1)
#             X = tensaug.time_warp(X.clone(), W=10)
#             X = tensaug.time_mask(X, T=50, max_masks=5)
#             X = tensaug.freq_mask(X, F=50, max_masks=5)
#
#             # remove "batch" dimension
#             X = X[0, :]
#
#             # Transform shape from 1 dimension to 3 dimensions
#             X = torch.cat([X] * 3, dim=0)  # dim=1)
#
#         return X
#
#     def overlay_random_image(self, original_image, audio_length, original_labels):
#         """Overlay an image from another class
#
#         Select a random file from a different class. Trim if necessary to the
#         same length as the given image. Overlay the images on top of each other
#         with a weight
#         """
#         import random
#
#         # Select a random file containing none of the classes this file contains
#         if self.overlay_class == "different":
#             good_choice = False  # keep picking random ones until we satisfy criteria
#             while not good_choice:
#                 candidate_idx = random.randint(0, len(self.df))
#                 # check if this choice meets criteria
#                 labels_overlap = sum(
#                     self.df.values[candidate_idx, :] * original_labels.values
#                 )
#                 good_choice = int(labels_overlap) == 0
#
#             # TODO: check that this is working as expected
#             overlay_path = self.df.index[candidate_idx]
#
#         else:  # Select a random file from a class of choice (may be slow)
#             choose_from = self.df[self.df[self.overlay_class] == 1]
#             overlay_path = np.random.choice(choose_from.index.values)
#
#         overlay_audio = Audio.from_file(
#             overlay_path, sample_rate=self.audio_sample_rate
#         )
#
#         # trim to same length as main clip
#         overlay_audio_length = overlay_audio.duration()
#         if overlay_audio_length < audio_length and not self.extend_short_clips:
#             raise ValueError(
#                 f"the length of the overlay file ({overlay_audio_length} sec) was less than the length of the original file ({audio_length} sec). To extend short clips, use extend_short_clips=True"
#             )
#         elif overlay_audio_length > audio_length:
#             from opensoundscape.preprocess import random_audio_trim
#
#             overlay_audio = random_audio_trim(
#                 overlay_audio, audio_length, self.extend_short_clips
#             )
#
#         overlay_image = self.audio_to_img(overlay_audio)
#         # overlay_spectrogram = Spectrogram.from_audio(overlay_audio)
#         # overlay_image = spectrogram.to_image(shape=(self.width, self.height), mode="L")
#
#         # add blur?? Miao had this but not sure it should be here
#         blur_r = np.random.randint(0, 8) / 10
#         overlay_image = overlay_image.filter(ImageFilter.GaussianBlur(radius=blur_r))
#
#         # Select weight of overlay; <0.5 means more emphasis on original image
#         if self.overlay_weight == "random":
#             weight = np.random.randint(2, 5) / 10
#         else:
#             weight = self.overlay_weight
#
#         # use a weighted sum to overlay (blend) the images
#         return Image.blend(original_image, overlay_image, weight)
#
#     def add_overlays(self, image):
#         # here is the first deviation from the routine
#         # requires access to multiple rows of df
#         # add a blended/overlayed image from another class directly on top
#         # this logic doesn't quite work for multi-label
#         for _ in range(self.max_overlay_num):
#             if self.overlay_prob > np.random.uniform():
#                 image = self.overlay_random_image(
#                     original_image=image,
#                     audio_length=self.audio_length,
#                     original_labels=row,
#                 )
#             else:
#                 break
#         return image
#
#     def upsample(self):
#         raise NotImplementedError("Upsampling is not implemented yet")
#
#     def __len__(self):
#         return self.df.shape[0]
#
#     def __getitem__(self, item_idx):
#
#         df_row = self.df.iloc[item_idx]
#         audio_path = Path(df_row.name)  # the index contains the audio path
#
#         x = audio_path  # since x will change types, we give it a generic name
#         for pipeline_element in self.pipeline:
#             # the key is the funciton, the value is an on/off switch
#             if self.pipeline[pipeline_element]:  # if False, we skip this step
#                 x = pipeline_element(x)  # apply the transform
#
#         # explicit version
#         # audio = self.load_audio(audio_path)
#         # audio = self.audio_transform(audio)  # currently does nothing
#         # img = self.audio_to_img(audio)  # to spectrogram, then image
#         # img = self.img_transform(img)  # includes overlays
#         # tensor = self.img_to_tensor(img)
#         # tensor = self.tensor_transform(tensor)  # includes tensor_augment
#         # x=tensor
#
#         # for debugging: save the tensor after all augmentations/transforms
#         if self.debug:
#             from torchvision.utils import save_image
#
#             save_image(x, f"{self.debug}/{audio_path.stem}_{time()}.png")
#
#         # Return data : label pairs (training/validation)
#         if self.return_labels:
#             return {"X": x, "y": torch.from_numpy(df_row.values)}
#
#         # Return data only (prediction)
#         return {"X": x}


from opensoundscape import preprocess
from opensoundscape.preprocess import ParameterRequiredError

# class Elements():
#     """this is an empty object which holds transform instances"""
#     def __init(self):
#         pass
#
# class BasePreprocessor(torch.utils.data.Dataset):
#     def __init__(self, df, return_labels):
#         self.df=df
#         self.return_labels = return_labels
#
#         # a collection of Instances of preprocess module transforms
#         self.elements = Elements() #access self.elements.LoadAudio, etc...
#         self.elements.load_audio = opensoundscape.preprocess.LoadAudio()
#
#         self.pipeline = [
#             self.elements.load_audio
#         ]
#
#     def def __len__(self):
#         return self.df.shape[0]
#
#     def __getitem__(self, item_idx):
#
#         df_row = self.df.iloc[item_idx]
#         x = Path(df_row.name)  # the index contains the audio path
#
#         for pipeline_element in self.pipeline:
#             x = pipeline_element(x)  # apply the transform
#
#         # Return data : label pairs (training/validation)
#         if self.return_labels:
#             return {"X": x, "y": torch.from_numpy(df_row.values)}
#
#         # Return data only (prediction)
#         return {"X": x}
#
# class AudioToImagePreprocessor(opensoundscape.datasets.BasePreprocessor):
#     def __init__(self, df, return_labels, overlay_df=None):
#         super(AudioToImagePreprocessor,self).__init__(df, return_labels)
#         self.overlay_df = overlay_df
#
#         # self.elements.load_audio = opensoundscape.preprocess.LoadAudio()
#         #add more elements
#
#         self.pipeline = [
#             self.elements.load_audio
#             #add more pipeline
#         ]
#
#     def def __len__(self):
#         return self.df.shape[0]
#
#     def __getitem__(self, item_idx):
#
#         df_row = self.df.iloc[item_idx]
#         x = Path(df_row.name)  # the index contains the audio path
#
#         for pipeline_element in self.pipeline:
#             x = pipeline_element(x)  # apply the transform
#
#         for debugging: save the tensor after all augmentations/transforms
#         if self.debug:
#             from torchvision.utils import save_image
#             save_image(x, f"{self.debug}/{audio_path.stem}_{time()}.png")
#
#         # Return data : label pairs (training/validation)
#         if self.return_labels:
#             return {"X": x, "y": torch.from_numpy(df_row.values)}
#
#         # Return data only (prediction)
#         return {"X": x}


class BasePreprocessor(torch.utils.data.Dataset):
    def __init__(self, df, return_labels=True):

        self.df = df
        self.return_labels = return_labels
        self.labels = df.columns

        # actions: a collection of instances of BaseAction child classes
        self.actions = preprocess.ActionContainer()

        # pipeline: an ordered list of operations to conduct on each file,
        # each pulled from self.actions
        self.pipeline = []

    def __len__(self):
        return self.df.shape[0]

    def __getitem__(self, item_idx):

        df_row = self.df.iloc[item_idx]
        x = Path(df_row.name)  # the index contains a path to a file

        for pipeline_element in self.pipeline:
            try:
                x = pipeline_element.go(x)
            except ParameterRequiredError:  # need to pass labels
                x, df_row = pipeline_element.go(x, df_row)

        # Return sample & label pairs (training/validation)
        if self.return_labels:
            labels = torch.from_numpy(df_row.values)
            return {"X": x, "y": labels}

        # Return sample only (prediction)
        return {"X": x}

    def class_counts_cal(self):
        """count number of each label"""
        print("Warning: check if this is the correct behavior")
        labels = self.df.columns
        counts = np.sum(self.df.values, 0)
        return labels, counts


class AudioLoadingPreprocessor(BasePreprocessor):
    """creates Audio objects from file paths"""

    def __init__(self, df, return_labels=True):

        super(AudioLoadingPreprocessor, self).__init__(df, return_labels=return_labels)

        # add an AudioLoader to our (currently empty) action toolkit
        self.actions.load_audio = preprocess.AudioLoader()

        # add the action to our (currently empty) pipeline
        self.pipeline.append(self.actions.load_audio)


class AudioToImagePreprocessor(BasePreprocessor):
    """loads audio paths, performs various augmentations, returns tensor


    perhaps this should be called something more specific, and a more generic
    AudioToImagePreprocessor should contain only the basics
    """

    def __init__(
        self,
        df,
        audio_length=None,
        return_labels=True,
        augmentation=True,
        debug=None,
        overlay_df=None,
    ):

        super(AudioToImagePreprocessor, self).__init__(df, return_labels=return_labels)

        self.audio_length = audio_length
        self.augmentation = augmentation
        self.return_labels = return_labels
        self.debug = debug

        # add each action to our tool kit, then to pipeline
        self.actions.load_audio = preprocess.AudioLoader()
        self.pipeline.append(self.actions.load_audio)

        self.actions.trim_audio = preprocess.AudioTrimmer()
        self.pipeline.append(self.actions.trim_audio)

        self.actions.to_spec = preprocess.AudioToSpectrogram()
        self.pipeline.append(self.actions.to_spec)

        self.actions.to_img = preprocess.SpecToImg()
        self.pipeline.append(self.actions.to_img)

        # should make one without overlay, then subclass and add overlay
        if self.augmentation:
            self.actions.overlay = preprocess.ImgOverlay(
                overlay_df=overlay_df,
                audio_length=self.audio_length,
                prob_overlay=1,
                max_overlay=1,
                overlay_class=None,
                # might not update with changes?
                loader_pipeline=self.pipeline[0:4],
                update_labels=True,
            )
            self.pipeline.append(self.actions.overlay)

            # color jitter and affine can be applied to img or tensor
            self.actions.color_jitter = preprocess.TorchColorJitter()
            self.pipeline.append(self.actions.color_jitter)

            self.actions.random_affine = preprocess.TorchRandomAffine()
            self.pipeline.append(self.actions.random_affine)

        self.actions.to_tensor = preprocess.ImgToTensor()
        self.pipeline.append(self.actions.to_tensor)

        self.actions.normalize = preprocess.TensorNormalize()
        self.pipeline.append(self.actions.normalize)

        if self.augmentation:
            self.actions.tensor_aug = preprocess.TensorAugment()
            self.pipeline.append(self.actions.tensor_aug)

        if self.debug is not None:
            self.actions.save_img = preprocess.SaveTensorToDisk(self.debug)
            self.pipeline.append(self.actions.save_img)

    # now that there is an action for saving images, don't need to overrride
    #
    # def __getitem__(self, item_idx):
    #     """Overrides base class to allow debug=path (save outputs to file)"""
    #
    #     df_row = self.df.iloc[item_idx]
    #     x = Path(df_row.name)  # the index contains a path to a file
    #
    #     for pipeline_element in self.pipeline:
    #         try:
    #             x = pipeline_element.go(x)
    #         except ParameterRequiredError:  # need to pass labels
    #             x = pipeline_element.go(x, df_row)
    #
    #     # for debugging: save the tensor after all augmentations/transforms
    #     if self.debug:
    #         from torchvision.utils import save_image
    #
    #         save_image(x, f"{self.debug}/{audio_path.stem}_{time()}.png")
    #
    #     # Return data : label pairs (training/validation)
    #     if self.return_labels:
    #         return {"X": x, "y": torch.from_numpy(df_row.values)}
    #
    #     # Return data only (prediction)
    #     return {"X": x}


class ResnetMultilabelPreprocessor(BasePreprocessor):
    """loads audio paths, performs various augmentations, returns tensor"""

    def __init__(
        self,
        df,
        audio_length=None,
        return_labels=True,
        augmentation=True,
        debug=None,
        overlay_df=None,
    ):

        super(ResnetMultilabelPreprocessor, self).__init__(
            df, return_labels=return_labels
        )

        self.audio_length = audio_length
        self.augmentation = augmentation
        self.return_labels = return_labels
        self.debug = debug

        # add each action to our tool kit, then to pipeline
        self.actions.load_audio = preprocess.AudioLoader()
        self.pipeline.append(self.actions.load_audio)

        self.actions.trim_audio = preprocess.AudioTrimmer()
        self.pipeline.append(self.actions.trim_audio)

        self.actions.to_spec = preprocess.AudioToSpectrogram()
        self.pipeline.append(self.actions.to_spec)

        self.actions.to_img = preprocess.SpecToImg()
        self.pipeline.append(self.actions.to_img)

        # should make one without overlay, then subclass and add overlay
        if self.augmentation:
            self.actions.overlay = preprocess.ImgOverlay(
                overlay_df=overlay_df,
                audio_length=self.audio_length,
                prob_overlay=0.5,
                max_overlay=2,
                overlay_weight=[0.2, 0.5],
                # this pipeline might not update with changes to preprocessor?
                loader_pipeline=self.pipeline[0:4],
                update_labels=True,
            )
            self.pipeline.append(self.actions.overlay)

            # color jitter and affine can be applied to img or tensor
            # here, we choose to apply them to the PIL.Image
            self.actions.color_jitter = preprocess.TorchColorJitter()
            self.pipeline.append(self.actions.color_jitter)

            self.actions.random_affine = preprocess.TorchRandomAffine()
            self.pipeline.append(self.actions.random_affine)

        self.actions.to_tensor = preprocess.ImgToTensor()
        self.pipeline.append(self.actions.to_tensor)

        if self.augmentation:
            self.actions.tensor_aug = preprocess.TensorAugment()
            self.pipeline.append(self.actions.tensor_aug)

            self.actions.add_noise = preprocess.TensorAddNoise(std=1.0)
            self.pipeline.append(self.actions.add_noise)

        self.actions.normalize = preprocess.TensorNormalize()
        self.pipeline.append(self.actions.normalize)

        if self.debug is not None:
            self.actions.save_img = preprocess.SaveTensorToDisk(self.debug)
            self.pipeline.append(self.actions.save_img)

    # def __getitem__(self, item_idx):
    #     """Overrides base class to allow debug=path (save outputs to file)"""
    #
    #     df_row = self.df.iloc[item_idx]
    #     x = Path(df_row.name)  # the index contains a path to a file
    #
    #     for pipeline_element in self.pipeline:
    #         try:
    #             x = pipeline_element.go(x)
    #         except ParameterRequiredError:  # need to pass labels
    #             #note: the function returns a new set of labels!
    #             x, df_row = pipeline_element.go(x, df_row)
    #
    #     # for debugging: save the tensor after all augmentations/transforms
    #     if self.debug:
    #         from torchvision.utils import save_image
    #         save_image(x, f"{self.debug}/{audio_path.stem}_{time()}.png")
    #
    #     # Return data : label pairs (training/validation)
    #     if self.return_labels:
    #         return {"X": x, "y": torch.from_numpy(df_row.values)}
    #
    #     # Return data only (prediction)
    #     return {"X": x}

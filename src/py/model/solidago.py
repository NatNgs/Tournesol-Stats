import zipfile
from abc import ABC, abstractmethod
from functools import cached_property
from typing import BinaryIO, Optional, Union
from urllib.request import urlretrieve

import pandas as pd

class TournesolInput(ABC):
    SCALING_CALIBRATION_MIN_TRUST_SCORE = 0.1
    MAX_SCALING_CALIBRATION_USERS = 100

    @abstractmethod
    def get_comparisons(
        self,
        criteria: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> pd.DataFrame:
        """Fetch data about comparisons submitted by users

        Returns:
        - comparisons_df: DataFrame with columns
            * `user_id`: int
            * `entity_a`: int or str
            * `entity_b`: int or str
            * `criteria`: str
            * `score`: float
            * `score_max`: int
            * `weight`: float
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def ratings_properties(self) -> pd.DataFrame:
        """Fetch data about contributor ratings properties

        Returns:
        - ratings_df: DataFrame with columns
            * `user_id`: int
            * `entity_id`: int or str
            * `is_public`: bool
            * `is_scaling_calibration_user`: bool
            * `trust_score`: float
        """
        raise NotImplementedError

    @abstractmethod
    def get_individual_scores(
        self,
        user_id: Optional[int] = None,
        entity_id: Optional[str] = None,
        criteria: Optional[str] = None,
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def get_collective_scores(
        self,
        entity_id: Optional[str] = None,
        criteria: Optional[str] = None,
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def get_vouches(self):
        """Fetch data about vouches shared between users

        Returns:
        - DataFrame with columns
            * `voucher`: int, user_id of the user who gives the vouch
            * `vouchee`: int, user_id of the user who receives the vouch
            * `vouch`: float, value of this vouch
        """
        raise NotImplementedError

    def get_users(self):
        users = self.ratings_properties.groupby("user_id").first()[["trust_score"]]
        users["is_pretrusted"] = users["trust_score"] >= 0.8
        return users

    def get_pipeline_kwargs(self, criterion: str):
        ratings_properties = self.ratings_properties
        users = self.get_users()
        vouches = self.get_vouches()
        comparisons = self.get_comparisons(criteria=criterion)
        entities_ids = set(comparisons["entity_a"].unique()) | set(
            comparisons["entity_b"].unique()
        )
        entities = pd.DataFrame(index=list(entities_ids))

        return {
            "users": users,
            "vouches": vouches,
            "entities": entities,
        }


class TournesolInputFromPublicDataset(TournesolInput):
    def __init__(self, dataset_zip: Union[str, BinaryIO]):
        if isinstance(dataset_zip, str) and (
            dataset_zip.startswith("http://") or dataset_zip.startswith("https://")
        ):
            dataset_zip, _headers = urlretrieve(dataset_zip)  # nosec B310

        with zipfile.ZipFile(dataset_zip) as zip_file:
            with (zipfile.Path(zip_file) / "users.csv").open(mode="rb") as users_file:
                # keep_default_na=False is required otherwise some public usernames
                # such as "NA" are converted to float NaN.
                self.users = pd.read_csv(users_file, keep_default_na=False)
                self.users.index.name = "user_id"
                # Fill trust_score on newly created users for which it was not computed yet
                self.users.trust_score = pd.to_numeric(self.users.trust_score).fillna(0.0)

                self.username_to_user_id = pd.Series(
                    data=self.users.index, index=self.users["public_username"]
                )

            with (zipfile.Path(zip_file) / "comparisons.csv").open(mode="rb") as comparison_file:
                # keep_default_na=False is required otherwise some public usernames
                # such as "NA" are converted to float NaN.
                self.comparisons = pd.read_csv(comparison_file, keep_default_na=False)
                self.entity_id_to_video_id = pd.Series(
                    list(set(self.comparisons.video_a) | set(self.comparisons.video_b)),
                    name="video_id",
                )
                self.video_id_to_entity_id = {
                    video_id: entity_id
                    for (entity_id, video_id) in self.entity_id_to_video_id.items()
                }
                self.comparisons["entity_a"] = self.comparisons["video_a"].map(
                    self.video_id_to_entity_id
                )
                self.comparisons["entity_b"] = self.comparisons["video_b"].map(
                    self.video_id_to_entity_id
                )
                self.comparisons.drop(columns=["video_a", "video_b"], inplace=True)
                self.comparisons = self.comparisons.join(
                    self.username_to_user_id, on="public_username"
                )

                # List of all groups of public_username,criteria,entity_id present in comparisons
                user_entity_criteria_pairs = pd.concat([
                    self.comparisons[["public_username", "entity_a", "criteria"]]
                        .rename(columns={"entity_a": "entity_id"}),
                    self.comparisons[["public_username", "entity_b", "criteria"]]
                        .rename(columns={"entity_b": "entity_id"})
                ])  # Will contain duplicates not to be removed

            with (zipfile.Path(zip_file) / "vouchers.csv").open(mode="rb") as vouchers_file:
                # keep_default_na=False is required otherwise some public usernames
                # such as "NA" are converted to float NaN.
                self.vouchers = pd.read_csv(vouchers_file, keep_default_na=False)

            with (zipfile.Path(zip_file) / "collective_criteria_scores.csv").open(mode="rb") as collective_scores_file:
                # keep_default_na=False is required otherwise some public usernames
                # such as "NA" are converted to float NaN.
                self.collective_scores = pd.read_csv(collective_scores_file, keep_default_na=False)
                # Convert video to entity_id
                self.collective_scores["entity_id"] = self.collective_scores["video"].map(
                    self.video_id_to_entity_id
                )
                self.collective_scores.drop(columns=["video"], inplace=True)

                # Add a column "comparisons", as the number of comparisons made to this video
                self.collective_scores["comparisons"] = self.collective_scores.merge(
                    user_entity_criteria_pairs
                        .groupby(["entity_id", "criteria"])
                        .size()
                        .reset_index(name="comparisons"),
                    how="left",  # Keep all data from collective_criteria_scores in same order
                    on=["entity_id", "criteria"],
                )["comparisons"]

                # Add a column "users", as the number of different users who have rated this video
                self.collective_scores["users"] = self.collective_scores.merge(
                    user_entity_criteria_pairs
                        .groupby(["entity_id", "criteria"])
                        .public_username
                        .nunique()
                        .reset_index(name="users"),
                    how="left",  # Keep all data from collective_criteria_scores in same order
                    on=["entity_id", "criteria"],
                )["users"]

            with (zipfile.Path(zip_file) / "individual_criteria_scores.csv").open(mode="rb") as individual_scores_file:
                # keep_default_na=False is required otherwise some public usernames
                # such as "NA" are converted to float NaN.
                self.individual_scores = pd.read_csv(individual_scores_file, keep_default_na=False)
                # Convert video to entity_id
                self.individual_scores["entity_id"] = self.individual_scores["video"].map(
                    self.video_id_to_entity_id
                )
                self.individual_scores.drop(columns=["video"], inplace=True)

                # Append as a new column the number of comparison made for every user,video,criteria
                self.individual_scores["comparisons"] = self.individual_scores.merge(
                    user_entity_criteria_pairs
                        .groupby(["public_username", "entity_id", "criteria"])
                        .size()
                        .reset_index(name="comparisons"),
                    how="left",  # Keep all data from collective_criteria_scores in same order
                    on=["public_username", "entity_id", "criteria"],
                )["comparisons"]
                self.individual_scores = self.individual_scores.join(
                    self.username_to_user_id,
                    on="public_username"
                )

    @classmethod
    def download(cls) -> "TournesolInputFromPublicDataset":
        return cls(dataset_zip="https://api.tournesol.app/exports/all")

    def get_comparisons(self, criteria=None, user_id=None) -> pd.DataFrame:
        dtf = self.comparisons.copy(deep=False)
        if criteria is not None:
            dtf = dtf[dtf.criteria == criteria]
        if user_id is not None:
            dtf = dtf[dtf.user_id == user_id]
        dtf["weight"] = 1
        if "score_max" not in dtf:
            # For compatibility with older datasets
            dtf["score_max"] = 10
        return dtf[[
            "user_id",
            "entity_a",
            "entity_b",
            "criteria",
            "score",
            "score_max",
            "weight"
        ]]

    @cached_property
    def ratings_properties(self):
        user_entities_pairs = pd.Series(
            iter(
                set(self.comparisons.groupby(["user_id", "entity_a"]).indices.keys())
                | set(self.comparisons.groupby(["user_id", "entity_b"]).indices.keys())
            )
        )
        dtf = pd.DataFrame([*user_entities_pairs], columns=["user_id", "entity_id"])
        dtf["is_public"] = True
        dtf["trust_score"] = dtf["user_id"].map(self.users["trust_score"])
        scaling_calibration_user_ids = (
            dtf[dtf.trust_score > self.SCALING_CALIBRATION_MIN_TRUST_SCORE]["user_id"]
            .value_counts(sort=True)[: self.MAX_SCALING_CALIBRATION_USERS]
            .index
        )
        dtf["is_scaling_calibration_user"] = dtf["user_id"].isin(scaling_calibration_user_ids)
        return dtf

    def get_individual_scores(
        self,
        user_id: Optional[int] = None,
        entity_id: Optional[str] = None,
        criteria: Optional[str] = None,
    ) -> pd.DataFrame:
        dtf = self.individual_scores
        if criteria is not None:
            dtf = dtf[dtf.criteria == criteria]
        if user_id is not None:
            dtf = dtf[dtf.user_id == user_id]
        if entity_id is not None:
            dtf = dtf[dtf.entity_id == entity_id]
        return dtf[[
            "user_id",
            "entity_id",
            "criteria",
            "score",
            "uncertainty",
            "voting_right",
            "comparisons"
        ]]

    def get_collective_scores(
        self,
        entity_id: Optional[str] = None,
        criteria: Optional[str] = None,
    ) -> pd.DataFrame:
        dtf = self.collective_scores
        if criteria is not None:
            dtf = dtf[dtf.criteria == criteria]
        if entity_id is not None:
            dtf = dtf[dtf.entity_id == entity_id]
        return dtf[["entity_id", "criteria", "score", "uncertainty", "users", "comparisons"]]

    def get_vouches(self):
        vouchers = self.vouchers[
            self.vouchers.by_username.isin(self.username_to_user_id.index)
            & self.vouchers.to_username.isin(self.username_to_user_id.index)
        ]
        return pd.DataFrame(
            {
                "voucher": vouchers.by_username.map(self.username_to_user_id),
                "vouchee": vouchers.to_username.map(self.username_to_user_id),
                "vouch": vouchers.value,
            }
        )

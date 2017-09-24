import copy
import pandas as pd
from pypokerengine.players import BasePokerPlayer
from bot.util.features import *
from bot.util.model import MergeModel
from catboost import CatBoostClassifier, CatBoostRegressor
import pickle


class ManulPlayer6Final(BasePokerPlayer):
    model_dir = 'model/final'
    names = ['KillFish', 'dannyace', 'fcll']

    model_call = MergeModel(len(names), model_dir, 'call')
    model_raise = MergeModel(len(names), model_dir, 'raise')
    model_raise_amount = MergeModel(len(names), model_dir, 'raise_amount', classifier=CatBoostRegressor)

    def __init__(self, model_num=None):
        super().__init__()
        self.names = ManulPlayer6Final.names
        self.model_call = ManulPlayer6Final.model_call
        self.model_raise = ManulPlayer6Final.model_raise
        self.model_raise_amount = ManulPlayer6Final.model_raise_amount
        self.model_num = model_num

    def predict_action(self, X, valid_actions):
        if self.model_call.predict(X, self.model_num)[0][0] > 0:
            if self.model_raise.predict(X, self.model_num)[0][0] > 0:
                if (len(valid_actions) > 2) and valid_actions[2]['amount']['min'] != -1:
                    amount = self.sb * int(round(self.model_raise_amount.predict(X, self.model_num)[0][0]))
                    amount = max(valid_actions[2]['amount']['min'], amount)
                    amount = min(valid_actions[2]['amount']['max'], amount)
                    return valid_actions[2]['action'], amount
                else:
                    return valid_actions[1]['action'], valid_actions[1]['amount']
            else:
                return valid_actions[1]['action'], valid_actions[1]['amount']
        else:
            return valid_actions[0]['action'], valid_actions[0]['amount']

    def declare_action(self, valid_actions, hole_card, round_state, bot_state=None):
        on_declare_action(self.features, self.uuid, valid_actions, round_state)

        features = copy.deepcopy(self.features)
        X, _ = clean_features([features])
        X = pd.DataFrame(X)

        action, amount = self.predict_action(X, valid_actions)
        # print(action, amount)

        return self.sanity_check(action, amount, valid_actions)

    def sanity_check(self, action, amount, valid_actions):
        if valid_actions[1]['amount'] == 0:
            if action == 'fold':
                return valid_actions[1]['action'], valid_actions[1]['amount']

        return action, amount

    def receive_game_start_message(self, game_info):
        self.features = {}
        self.sb = game_info['rule']['small_blind_amount']
        on_game_start(self.features, self.uuid, game_info)

    def receive_round_start_message(self, round_count, hole_card, seats):
        on_round_start(self.features, self.uuid, round_count, hole_card, seats)

    def receive_street_start_message(self, street, round_state):
        on_street_start(self.features, self.uuid, street, round_state)

    def receive_game_update_message(self, action, round_state):
        on_player_action(self.features, self.uuid, action)

    def receive_round_result_message(self, winners, hand_info, round_state):
        on_round_result(self.features, self.uuid, winners, hand_info)

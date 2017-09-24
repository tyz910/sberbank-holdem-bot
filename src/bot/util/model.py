import pandas as pd
from catboost import CatBoostClassifier
from pypokerengine.engine.deck import Deck
from pypokerengine.engine.round_manager import RoundManager


class ModelPool(object):
    def __init__(self, num, dir, classifier=CatBoostClassifier):
        self.models = []
        for i in range(num):
            model = classifier()
            model.load_model(dir + str(i) + '.model')
            self.models.append(model)

    def predict(self, X):
        predicts = {}
        for i, model in enumerate(self.models):
            predicts['model_' + str(i)] = model.predict(X)

        return pd.DataFrame(predicts, index=X.index).sort_index(axis=1)

    def predictModel(self, X, num=0):
        return self.models[num].predict(X)


class MergeModel(object):
    def __init__(self, num, dir, name, classifier=CatBoostClassifier):
        self.model_pool = ModelPool(num, dir + '/pool/' + name + '/', classifier=classifier)
        self.model = classifier()
        self.model.load_model(dir + '/' + name + '.model')

    def predict(self, X, model_num=None):
        if model_num is not None:
            return pd.DataFrame(self.predictModel(X, model_num), index=X.index)

        X_pool = self.model_pool.predict(X)
        return pd.DataFrame(self.model.predict(X_pool), index=X.index)

    def predictModel(self, X, num=0):
        return self.model_pool.predictModel(X, num)


class PokerSim(object):
    def __init__(self, num_players, num_rounds):
        self.round_count = 0
        self.community_from = 0
        self.cards = []
        for i in range(num_rounds):
            d = Deck()
            d.shuffle()
            cards = {'hole': [], 'community': d.draw_cards(5)}
            for j in range(num_players):
                cards['hole'].append(d.draw_cards(2))

            self.cards.append(cards)

    def deal_holecard(self, players):
        self.community_from = 0

        for i, player in enumerate(players):
            player.add_holecard(self.cards[self.round_count - 1]['hole'][i])

    def deal_community_card(self, state, num):
        self.community_to = self.community_from + num

        cards = self.cards[self.round_count - 1]['community'][self.community_from:self.community_to]
        for card in cards:
            state["table"].add_community_card(card)

        self.community_from = self.community_to

        return RoundManager._RoundManager__forward_street(state)
from pypokerengine.engine.hand_evaluator import HandEvaluator
from pypokerengine.utils.card_utils import gen_cards, estimate_hole_card_win_rate
import copy
import pandas as pd
import time
import pickle


sim3_proba_cache = {}

try:
    preflop_odds = pd.read_csv('data/preflop_odds.txt', sep='\t', index_col=0)
except FileNotFoundError:
    preflop_odds = pd.read_csv('src/data/preflop_odds.txt', sep='\t', index_col=0)
preflop_odds.columns = range(1, 10)


class Profiler(object):
    bank = 0

    def __enter__(self):
        self._startTime = time.time()

    def __exit__(self, type, value, traceback):
        Profiler.bank += time.time() - self._startTime
        print("Elapsed time: {:.3f} sec".format(Profiler.bank))


def norm_rounds(i, max_round):
    if i < 10:
        return i

    return int(10 + (i - 10) * (40 / (max_round - 10)))


def get_card_preflop_odds(cards, num_players):
    c1 = cards[0]
    c2 = cards[1]
    c1_name = str(c1)[1]
    c2_name = str(c2)[1]

    if c1_name == c2_name:
        cards_name = c1_name + c2_name
    else:
        cards_name = c1_name + c2_name if c1.rank > c2.rank else c2_name + c1_name
        cards_name += 's' if c1.suit == c2.suit else 'o'

    global preflop_odds

    try:
        odds = preflop_odds.loc[cards_name][min(2, num_players - 1)]
    except Exception:
        odds = 0

    return odds


def get_card_sub_features(cards):
    max_rank = 0
    ranks = {}
    suits = {}

    for c in cards:
        max_rank = max(max_rank, c.rank)
        
        if c.rank not in ranks:
            ranks[c.rank] = 1
        else:
            ranks[c.rank] += 1

        if c.suit not in suits:
            suits[c.suit] = 1
        else:
            suits[c.suit] += 1

    f = {
        'max_rank': max_rank
    }
    
    for num in [4, 3, 2]:
        f['num' + str(num)] = 0
        f['num' + str(num) + '_max_rank'] = 0
    
    for s in [2, 4, 8, 16]:
        f['suit' + str(s)] = 0

    for r in ranks:
        for num in [2, 3, 4]:
            if ranks[r] == num:
                f['num' + str(num)] += 1
                f['num' + str(num) + '_max_rank'] = max(f['num' + str(num) + '_max_rank'], r)
                break

    for s in suits:
        f['suit' + str(s)] = suits[s]

    return f


def get_card_features(hole, community):
    hole_card = gen_cards(hole)
    community_card = gen_cards(community)

    e = HandEvaluator.gen_hand_rank_info(hole_card, community_card)

    if len(community_card) > 0:
        e2 = HandEvaluator.gen_hand_rank_info(community_card, [])
    else:
        e2 = {'hand': {'high': 0, 'strength': 'HIGHCARD'}}

    f = {
        'hand_high': e['hand']['high'],
        'hand_strength': e['hand']['strength'],
        'hand_community_high': e2['hand']['high'],
        'hand_community_strength': e2['hand']['strength']
    }

    for name, cards in [('hole', hole_card), ('community', community_card)]:
        subf = get_card_sub_features(cards)
        for k in subf:
            f[name + '_' + k] = subf[k]

    del f['hole_num3']
    del f['hole_num4']
    del f['hole_num3_max_rank']
    del f['hole_num4_max_rank']

    if len(community_card) > 0:
        cache_key = ''.join(sorted(hole) + sorted(community))
        if cache_key in sim3_proba_cache:
            f['sim3_proba'] = sim3_proba_cache[cache_key]
        else:
            proba = estimate_hole_card_win_rate(nb_simulation=100, nb_player=3, hole_card=hole_card, community_card=community_card)
            sim3_proba_cache[cache_key] = f['sim3_proba'] = proba
    else:
        f['sim3_proba'] = 0

    return f


def on_cards_change(features, player_uuid):
    card_features = get_card_features(features['hole_card'], features['community_card'])
    for f in card_features:
        features['card_' + f] = card_features[f]


def on_game_start(features, player_uuid, game_info):
    features['small_blind_amount'] = game_info['rule']['small_blind_amount']
    features['initial_stack'] = game_info['rule']['initial_stack']
    features['total_stack'] = features['initial_stack'] * len(game_info['seats'])
    features['players'] = {}

    i = 0
    for seat in game_info['seats']:
        player = reg_player(features, seat['uuid'])
        if seat['uuid'] == player_uuid:
            player['me'] = True
            features['player_num'] = i

        player['num'] = i
        i += 1


def reg_player(features, uuid):
    player = features['players'][uuid] = {
        'me': False,
        'num': 0,
        'dealer': 0,
        'small_blind': 0,
        'big_blind': 0,
        'win_rounds': 0,
        'lose_rounds': 0,
        'win_rounds_nohand': 0,
        'stack': 0,
        'start_stack': 0,
        'hand_paid': 0,
        'hand_strength': 'HIGHCARD',
        'hand_hole_pairs': 0,
        'hand_hole_high': 0
    }

    for action in ['fold', 'call', 'raise']:
        player[action + '_rounds'] = 0
        player[action + '_in_round'] = 0
        player[action + '_in_street'] = 0
        for street in ['preflop', 'flop', 'turn', 'river']:
            player[action + '_in_' + street] = 0
            player[action + '_' + street + 's'] = 0

    player['preflop_actions'] = 0
    for street in ['flop', 'turn', 'river']:
        player[street + '_rounds'] = 0
        player[street + '_actions'] = 0

    return player


def on_round_start(features, player_uuid, round_count, hole_card, seats):
    features['round_count'] = round_count
    features['hole_card'] = hole_card
    features['community_card'] = []
    on_cards_change(features, player_uuid)

    for street in ['flop', 'turn', 'river']:
        features[street + '_card_sim3_proba'] = 0

    for seat in seats:
        player = features['players'][seat['uuid']]
        player['start_stack'] = seat['stack']
        player['state'] = seat['state']

        for action in ['fold', 'call', 'raise']:
            player[action + '_in_round'] = 0
            player[action + '_in_street'] = 0
            for street in ['preflop', 'flop', 'turn', 'river']:
                player[action + '_in_' + street] = 0


def on_street_start(features, player_uuid, street, round_state):
    features['street'] = street

    if street == 'preflop':
        features['preflop_odds'] = 0
        for _, player in features['players'].items():
            player['dealer'] = 1 if player['num'] == round_state['dealer_btn'] else 0
            player['small_blind'] = 1 if player['num'] == round_state['small_blind_pos'] else 0
            player['big_blind'] = 1 if player['num'] == round_state['big_blind_pos'] else 0

    if street == 'flop':
        features['community_card'] = round_state['community_card'][:3]

    if street == 'turn':
        features['community_card'] = round_state['community_card'][:4]

    if street == 'river':
        features['community_card'] = round_state['community_card'][:5]

    if street != 'preflop':
        on_cards_change(features, player_uuid)
        features[street + '_card_sim3_proba'] = features['card_sim3_proba']
        for _, player in features['players'].items():
            if player['state'] != 'folded':
                player[street + '_rounds'] += 1

            for action in ['fold', 'call', 'raise']:
                player[action + '_in_street'] = 0


def on_player_action(features, player_uuid, action):
    player = features['players'][action['player_uuid']]
    a = action['action']
    street = features['street']

    player[street + '_actions'] += 1
    player[a + '_in_round'] += 1
    player[a + '_in_street'] += 1
    player[a + '_in_' + street] += 1

    if player[a + '_in_round'] == 1:
        player[a + '_rounds'] += 1

    if player[a + '_in_' + street] == 1:
        player[a + '_' + street + 's'] += 1


def on_declare_action(features, player_uuid, valid_actions, round_state):
    features['pot'] = round_state['pot']['main']['amount']
    features['call_amount'] = valid_actions[1]['amount']
    features['raise_amount_min'] = valid_actions[2]['amount']['min']
    features['raise_amount_max'] = valid_actions[2]['amount']['max']

    for seat in round_state['seats']:
        player = features['players'][seat['uuid']]
        player['stack'] = seat['stack']
        player['state'] = seat['state']


def on_round_result(features, player_uuid, winners, hand_info):
    winner_uuids = []

    for winner in winners:
        winner_uuid = winner['uuid']
        winner_uuids.append(winner_uuid)
        player = features['players'][winner_uuid]
        player['win_rounds'] += 1
        player['win_rounds_nohand'] += min(len(hand_info), 1)


    for h in hand_info:
        h_uuid = h['uuid']
        if h_uuid not in winner_uuids:
            player = features['players'][h_uuid]
            player['lose_rounds'] += 1

            player['hand_paid'] = player['start_stack'] - player['stack']
            player['hand_strength'] = h['hand']['hand']['strength']
            player['hand_hole_high'] = h['hand']['hole']['high']
            if h['hand']['hole']['high'] == h['hand']['hole']['low']:
                player['hand_hole_pairs'] = h['hand']['hole']['high']
            else:
                player['hand_hole_pairs'] = 0


def win_eval(holes, community_card):
    return max([HandEvaluator.eval_hand(gen_cards(h), community_card) for h in holes])


def clean_features(data):
    max_players = 6
    strength = ["HIGHCARD", "ONEPAIR", "TWOPAIR", "THREECARD", "STRAIGHT", "FLASH", "FULLHOUSE", "FOURCARD", "STRAIGHTFLASH"]
    street = ["preflop", "flop", "turn", "river"]
    private_keys = None
    privates = []

    for X in data:
        if private_keys is None:
            private_keys = []
            for key in X:
                if key.startswith('private_'):
                    private_keys.append(key)

            if len(private_keys) > 0:
                private_keys += [
                    'private_best_hand'
                ]

        X['players_in_game'] = 0
        X['players_in_round'] = 0
        max_stack = 0

        for uuid, player in X['players'].items():
            if player['start_stack'] > 0:
                X['players_in_game'] += 1

            player['in_round'] = (player['state'] == 'participating')
            if player['in_round']:
                X['players_in_round'] += 1

            player['hand_strength'] = strength.index(player['hand_strength'])
            player['hand_paid'] = int(round(player['hand_paid'] / X['small_blind_amount']))
            player['paid'] = int(round((player['start_stack'] - player['stack']) / X['small_blind_amount']))
            max_stack = max(max_stack, player['stack'])

            player['to_left'] = 1 if player['num'] - X['player_num'] < 0 else 0

        if X['preflop_odds'] == 0:
            X['preflop_odds'] = round(get_card_preflop_odds(gen_cards(X['hole_card']), X['players_in_game']), 1)

        sorted_players = sorted(X['players'].values(), key=lambda x: (-x['me'], -x['in_round'], -x['to_left'], -x['num']))
        for i, player in enumerate(sorted_players[:max_players]):
            in_round = player['in_round']
            player['stack_rel_top_player'] = round(player['stack'] / max_stack, 1)
            player['stack_rel_game_start'] = round(player['stack'] / X['initial_stack'], 1)
            player['stack_rel_total'] = round(player['stack'] / X['total_stack'], 1)
            player['stack'] = int(round(player['stack'] / X['small_blind_amount']))

            del player['start_stack']
            del player['me']
            del player['state']
            del player['in_round']
            del player['num']
            del player['to_left']

            for s in ['preflop', 'flop', 'turn', 'river']:
                s_num = player[s + '_actions'] + 1
                del player[s + '_actions']
                for action in ['fold', 'call', 'raise']:
                    player[action + '_' + s + 's'] = round(player[action + '_' + s + 's'] / s_num, 1)

            player['win_rounds_nohand'] = round(player['win_rounds_nohand'] / (player['win_rounds'] + 1), 1)
            for round_counter in ['flop', 'turn', 'river', 'fold', 'call', 'raise', 'win', 'lose']:
                player[round_counter + '_rounds'] = round(player[round_counter + '_rounds'] / X['round_count'], 1)

            for k, v in player.items():
                X['player_' + str(i) + '_' + k] = v if in_round else -1

            if i == 0 and len(sorted_players) < max_players:
                for j in range(len(sorted_players), max_players):
                    for k, v in player.items():
                        X['player_' + str(j) + '_' + k] = -1

        X['card_hand_strength'] = strength.index(X['card_hand_strength'])
        X['card_hand_community_strength'] = strength.index(X['card_hand_community_strength'])
        X['street'] = street.index(X['street'])

        for money_field in ['call_amount', 'raise_amount_min', 'raise_amount_max', 'pot']:
            X[money_field] = int(round(X[money_field] / X['small_blind_amount']))

        if 'private_bot_action_amount' in X:
            X['private_bot_action_amount'] = int(round(X['private_bot_action_amount'] / X['small_blind_amount']))
            X['private_game_end_stack'] = int(round(X['private_game_end_stack'] / X['small_blind_amount']))
            X['private_round_end_stack_diff'] = int(round(X['private_round_end_stack_diff'] / X['small_blind_amount']))
            X['private_round_end_stack'] = int(round(X['private_round_end_stack'] / X['small_blind_amount']))

            community_card = gen_cards(X['private_community_card'])
            my_hand = win_eval([X['private_hole_card']], community_card)
            if len(X['private_opponent_hole_card']) > 0:
                op_hand = win_eval(X['private_opponent_hole_card'], community_card)
            else:
                op_hand = 0

            X['private_best_hand'] = 1 if my_hand >= op_hand else -1


        for k in ['hole_card', 'community_card', 'players', 'small_blind_amount', 'initial_stack', 'player_num', 'total_stack']:
            del X[k]

        private_row = {}
        for k in private_keys:
            private_row[k] = X[k]
            del X[k]

        privates.append(private_row)

    return data, privates


class GamePlayer(object):
    def __init__(self):
        self.data = []
        self.i = 1
        self._filter_actions = None
        self._filter_seats = None
        self.game_counter = -1

        global sim3_proba_cache
        with open('src/data/sim3_proba_cache.pickle', 'rb') as f:
            sim3_proba_cache = pickle.load(f)

    def get_features(self):
        X, y = clean_features(self.data)

        global sim3_proba_cache
        with open('src/data/sim3_proba_cache.pickle', 'wb') as f:
            pickle.dump(sim3_proba_cache, f)

        return pd.DataFrame(X), pd.DataFrame(y)

    def filter_actions(self, func):
        self._filter_actions = func

    def filter_seats(self, func):
        self._filter_seats = func

    def play_game(self, game):
        self.game_counter += 1
        features = {}
        max_stack = 0
        winner_uuid = None

        for seat in game['seats']:
            features[seat['uuid']] = {
                'private_game_num': self.game_counter,
                'private_game_win': False,
                'private_game_end_stack': seat['stack'],
                'private_bot_name': seat['name'],
                'private_bot_top': seat['top_player']
            }

            if seat['stack'] > max_stack:
                max_stack = seat['stack']
                winner_uuid = seat['uuid']

        features[winner_uuid]['private_game_win'] = True

        if self._filter_seats is not None:
            new_features = {}
            for uuid in features:
                if self._filter_seats(features[uuid]):
                    new_features[uuid] = features[uuid]
            features = new_features

        for uuid in features:
            on_game_start(features[uuid], uuid, game)

        for r in game['rounds']:
            seats = {}
            hole_cards = {}
            r['round_state']['pot']['main']['amount'] = 0

            for seat in r['round_state']['seats']:
                uuid = seat['uuid']

                if uuid in features:
                    hole_cards[uuid] = seat['hole_card']
                    features[uuid]['private_round_end_stack_diff'] = seat['stack'] - seat['start_stack']
                    features[uuid]['private_round_end_stack'] = seat['stack']
                    features[uuid]['private_round_end'] = seat['stack'] > seat['start_stack']
                    features[uuid]['private_community_card'] = r['round_state']['community_card']

                seats[uuid] = seat
                seat['stack'] = seat['start_stack']
                seat['state'] = seat['start_state']

            for h in r['hand_info']:
                uuid = h['uuid']
                if uuid in features:
                    features[uuid]['private_round_end'] = True

            for a in r['round_state']['action_histories']['preflop']:
                if a['action'] in ['BIGBLIND', 'SMALLBLIND']:
                    seats[a['uuid']]['stack'] += a['amount']

            for uuid in features:
                on_round_start(features[uuid], uuid, r['round_state']['round_count'], hole_cards[uuid], r['round_state']['seats'])

            for st in ['preflop', 'flop', 'turn', 'river']:
                if st in r['round_state']['action_histories']:
                    for uuid in features:
                        on_street_start(features[uuid], uuid, st, r['round_state'])

                    for a in r['round_state']['action_histories'][st]:
                        uuid = a['uuid']
                        money = 0
                        money += a['paid'] if 'paid' in a else 0
                        if money == 0:
                            money += a['add_amount'] if 'add_amount' in a else 0

                        if a['action'] not in ['BIGBLIND', 'SMALLBLIND']:
                            if not a['bot']['failed']:
                                if uuid in features:
                                    player_features = features[uuid]
                                    player_features['private_hole_card'] = player_features['hole_card']
                                    player_features['private_opponent_hole_card'] = []
                                    for _, s in seats.items():
                                        if (s['state'] != 'folded') and (s['uuid'] != uuid):
                                            player_features['private_opponent_hole_card'].append(s['hole_card'])

                                    on_declare_action(player_features, uuid, a['bot']['valid_actions'], r['round_state'])

                                    if not a['bot']['failed']:
                                        player_features['private_bot_action'] = a['action']
                                        player_features['private_bot_action_amount'] = a['amount'] if 'amount' in a else 0
                                        if not self._filter_actions or self._filter_actions(player_features):
                                            self.data.append(copy.deepcopy(player_features))

                                            self.i += 1
                                            if self.i % 10000 == 0:
                                                print(str(self.i), features)
                                                print()
                        else:
                            money = a['amount']

                        r['round_state']['pot']['main']['amount'] += money
                        seats[a['uuid']]['stack'] -= money

                        if a['action'] == 'FOLD':
                            seats[uuid]['state'] = 'folded'

                        if a['action'] not in ['BIGBLIND', 'SMALLBLIND']:
                            for uuid in features:
                                action = {
                                    'player_uuid': a['uuid'],
                                    'action': a['action'].lower(),
                                    'amount': 0 if a['action'] == 'FOLD' else a['amount']
                                }
                                on_player_action(features[uuid], uuid, action)

            for uuid in features:
                on_round_result(features[uuid], uuid, r['winners'], r['hand_info'])

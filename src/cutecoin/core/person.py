'''
Created on 11 févr. 2014

@author: inso
'''

import logging
import functools
import time

from ucoinpy.api import bma
from ucoinpy import PROTOCOL_VERSION
from ucoinpy.documents.certification import SelfCertification
from ucoinpy.documents.membership import Membership
from ..tools.exceptions import Error, PersonNotFoundError,\
                                        MembershipNotFoundError, \
                                        NoPeerAvailable
from PyQt5.QtCore import QMutex


def load_cache(json_data):
    for person_data in json_data['persons']:
        person = Person.from_json(person_data)
        Person._instances[person.pubkey] = person


def jsonify_cache():
    data = []
    for person in Person._instances.values():
        data.append(person.jsonify())
    return {'persons': data}


class cached(object):
    '''
    Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).
    Delete it to clear it from the cache
    '''
    def __init__(self, func):
        self.func = func

    def __call__(self, inst, community):
        inst._cache_mutex.lock()
        try:
            inst._cache[community.currency]
        except KeyError:
            inst._cache[community.currency] = {}

        try:
            value = inst._cache[community.currency][self.func.__name__]
        except KeyError:
            value = self.func(inst, community)
            inst._cache[community.currency][self.func.__name__] = value

        finally:
            inst._cache_mutex.unlock()

        return value

    def __repr__(self):
        '''Return the function's docstring.'''
        return self.func.__repr__

    def __get__(self, inst, objtype):
        if inst is None:
            return self.func
        return functools.partial(self, inst)


#TODO: Change Person to Identity ?
class Person(object):
    '''
    A person with a uid and a pubkey
    '''
    _instances = {}

    def __init__(self, uid, pubkey, cache):
        '''
        Initializing a person object.

        :param str uid: The person uid, also known as its uid on the network
        :param str pubkey: The person pubkey
        :param cache: The last returned values of the person properties.
        '''
        super().__init__()
        self.uid = uid
        self.pubkey = pubkey
        self._cache = cache
        self._cache_mutex = QMutex()

    @classmethod
    def lookup(cls, pubkey, community, cached=True):
        '''
        Get a person from the pubkey found in a community

        :param str pubkey: The person pubkey
        :param community: The community in which to look for the pubkey
        :param bool cached: True if the person should be searched in the
        cache before requesting the community.

        :return: A new person if the pubkey was unknown or\
        the known instance if pubkey was already known.
        '''
        if cached and pubkey in Person._instances:
            return Person._instances[pubkey]
        else:
            try:
                data = community.request(bma.wot.Lookup, req_args={'search': pubkey},
                                         cached=cached)
            except ValueError as e:
                if '404' in str(e):
                    raise PersonNotFoundError(pubkey, community.name)

            timestamp = 0

            for result in data['results']:
                if result["pubkey"] == pubkey:
                    uids = result['uids']
                    person_uid = ""
                    for uid_data in uids:
                        if uid_data["meta"]["timestamp"] > timestamp:
                            timestamp = uid_data["meta"]["timestamp"]
                            person_uid = uid_data["uid"]

                        person = cls(person_uid, pubkey, {})
                        Person._instances[pubkey] = person
                        logging.debug("{0}".format(Person._instances.keys()))
                        return person
        raise PersonNotFoundError(pubkey, community.name)

    @classmethod
    def from_metadata(cls, metadata):
        '''
        Get a person from a metadata dict.
        A metadata dict has a 'text' key corresponding to the person uid,
        and a 'id' key corresponding to the person pubkey.

        :param dict metadata: The person metadata
        :return: A new person if pubkey wasn't knwon, else the existing instance.
        '''
        uid = metadata['text']
        pubkey = metadata['id']
        if pubkey in Person._instances:
            return Person._instances[pubkey]
        else:
            person = cls(uid, pubkey, {})
            Person._instances[pubkey] = person
            return person

    @classmethod
    def from_json(cls, json_data):
        '''
        Create a person from json data

        :param dict json_data: The person as a dict in json format
        :return: A new person if pubkey wasn't known, else a new person instance.
        '''
        pubkey = json_data['pubkey']
        if pubkey in Person._instances:
            return Person._instances[pubkey]
        else:
            if 'name' in json_data:
                uid = json_data['name']
            else:
                uid = json_data['uid']
            if 'cache' in json_data:
                cache = json_data['cache']
            else:
                cache = {}

            person = cls(uid, pubkey, cache)
            Person._instances[pubkey] = person
            return person

    def selfcert(self, community):
        '''
        Get the person self certification.
        This request is not cached in the person object.

        :param community: The community target to request the self certification
        :return: A SelfCertification ucoinpy object
        '''
        data = community.request(bma.wot.Lookup, req_args={'search': self.pubkey})
        logging.debug(data)
        timestamp = 0

        for result in data['results']:
            if result["pubkey"] == self.pubkey:
                uids = result['uids']
                for uid_data in uids:
                    if uid_data["meta"]["timestamp"] > timestamp:
                        timestamp = uid_data["meta"]["timestamp"]
                        uid = uid_data["uid"]
                        signature = uid_data["self"]

                return SelfCertification(PROTOCOL_VERSION,
                                             community.currency,
                                             self.pubkey,
                                             timestamp,
                                             uid,
                                             signature)
        raise PersonNotFoundError(self.pubkey, community.name)

    @cached
    def get_join_date(self, community):
        '''
        Get the person join date.
        This request is not cached in the person object.

        :param community: The community target to request the join date
        :return: A datetime object
        '''
        try:
            search = community.request(bma.blockchain.Membership, {'search': self.pubkey})
            membership_data = None
            if len(search['memberships']) > 0:
                membership_data = search['memberships'][0]
                return community.get_block(membership_data['blockNumber']).mediantime
            else:
                return None
        except ValueError as e:
            if '400' in str(e):
                raise MembershipNotFoundError(self.pubkey, community.name)
        except Exception as e:
            logging.debug('bma.blockchain.Membership request error : ' + str(e))
            raise MembershipNotFoundError(self.pubkey, community.name)

#TODO: Manage 'OUT' memberships ? Maybe ?
    @cached
    def membership(self, community):
        '''
        Get the person last membership document.

        :param community: The community target to request the join date
        :return: The membership data in BMA json format
        '''
        try:
            search = community.request(bma.blockchain.Membership,
                                               {'search': self.pubkey})
            block_number = -1
            for ms in search['memberships']:
                if ms['blockNumber'] > block_number:
                    block_number = ms['blockNumber']
                    if 'type' in ms:
                        if ms['type'] is 'IN':
                            membership_data = ms
                    else:
                        membership_data = ms

            if membership_data is None:
                raise MembershipNotFoundError(self.pubkey, community.name)
        except ValueError as e:
            if '400' in str(e):
                raise MembershipNotFoundError(self.pubkey, community.name)
        except Exception as e:
            logging.debug('bma.blockchain.Membership request error : ' + str(e))
            raise MembershipNotFoundError(self.pubkey, community.name)

        return membership_data

    @cached
    def published_uid(self, community):
        try:
            data = community.request(bma.wot.Lookup,
                                     req_args={'search': self.pubkey},
                                     cached=cached)
        except ValueError as e:
            if '404' in str(e):
                return False

        timestamp = 0

        for result in data['results']:
            if result["pubkey"] == self.pubkey:
                uids = result['uids']
                person_uid = ""
                for uid_data in uids:
                    if uid_data["meta"]["timestamp"] > timestamp:
                        timestamp = uid_data["meta"]["timestamp"]
                        person_uid = uid_data["uid"]
                    if person_uid == self.uid:
                        return True
        return False

    @cached
    def is_member(self, community):
        '''
        Check if the person is a member of a community

        :param community: The community target to request the join date
        :return: True if the person is a member of a community
        '''
        try:
            certifiers = community.request(bma.wot.CertifiersOf, {'search': self.pubkey})
            return certifiers['isMember']
        except ValueError:
            return False
        except Exception as e:
            logging.debug('bma.wot.CertifiersOf request error : ' + str(e))
            return False

    @cached
    def certifiers_of(self, community):
        '''
        Get the list of this person certifiers

        :param community: The community target to request the join date
        :return: The list of the certifiers of this community in BMA json format
        '''
        try:
            certifiers = community.request(bma.wot.CertifiersOf, {'search': self.pubkey})
        except ValueError as e:
            logging.debug('bma.wot.CertifiersOf request ValueError : ' + str(e))
            try:
                data = community.request(bma.wot.Lookup, {'search': self.pubkey})
            except ValueError as e:
                logging.debug('bma.wot.Lookup request ValueError : ' + str(e))
                return list()

            # convert api data to certifiers list
            certifiers = list()
            # add certifiers of uid

            for result in data['results']:
                if result["pubkey"] == self.pubkey:
                    for uid_data in result['uids']:
                        for certifier_data in uid_data['others']:
                            for uid in certifier_data['uids']:
                            # add a certifier
                                certifier = {}
                                certifier['uid'] = uid
                                certifier['pubkey'] = certifier_data['pubkey']
                                certifier['isMember'] = certifier_data['isMember']
                                certifier['cert_time'] = dict()
                                certifier['cert_time']['medianTime'] = community.get_block(certifier_data['meta']['block_number']).mediantime
                                certifiers.append(certifier)

            return certifiers

        except Exception as e:
            logging.debug('bma.wot.CertifiersOf request error : ' + str(e))
            return list()

        return certifiers['certifications']

    def unique_valid_certifiers_of(self, community):
        certifier_list = self.certifiers_of(community)
        unique_valid = []
        #  add certifiers of uid
        for certifier in tuple(certifier_list):
            # add only valid certification...
            if community.certification_expired(certifier['cert_time']['medianTime']):
                continue

            # keep only the latest certification
            already_found = [c['pubkey'] for c in unique_valid]
            if certifier['pubkey'] in already_found:
                index = already_found.index(certifier['pubkey'])
                if certifier['cert_time']['medianTime'] > unique_valid[index]['cert_time']['medianTime']:
                    unique_valid[index] = certifier
            else:
                unique_valid.append(certifier)
        return unique_valid

    @cached
    def certified_by(self, community):
        '''
        Get the list of persons certified by this person

        :param community: The community target to request the join date
        :return: The list of the certified persons of this community in BMA json format
        '''
        try:
            certified_list = community.request(bma.wot.CertifiedBy, {'search': self.pubkey})
        except ValueError as e:
            logging.debug('bma.wot.CertifiersOf request ValueError : ' + str(e))
            try:
                data = community.request(bma.wot.Lookup, {'search': self.pubkey})
            except ValueError as e:
                logging.debug('bma.wot.Lookup request ValueError : ' + str(e))
                return list()

            certified_list = list()
            for result in data['results']:
                if result["pubkey"] == self.pubkey:
                    for certified in result['signed']:
                        certified['cert_time'] = dict()
                        certified['cert_time']['medianTime'] = certified['meta']['timestamp']
                        certified_list.append(certified)

            return certified_list

        except Exception as e:
            logging.debug('bma.wot.CertifiersOf request error : ' + str(e))
            return list()

        return certified_list['certifications']

    def unique_valid_certified_by(self, community):
        certified_list = self.certified_by(community)
        unique_valid = []
        #  add certifiers of uid
        for certified in tuple(certified_list):
            # add only valid certification...
            if community.certification_expired(certified['cert_time']['medianTime']):
                continue

            # keep only the latest certification
            already_found = [c['pubkey'] for c in unique_valid]
            if certified['pubkey'] in already_found:
                index = already_found.index(certified['pubkey'])
                if certified['cert_time']['medianTime'] > unique_valid[index]['cert_time']['medianTime']:
                    unique_valid[index] = certified
            else:
                unique_valid.append(certified)
        return unique_valid

    def membership_expiration_time(self, community):
        join_block = self.membership(community)['blockNumber']
        join_date = community.get_block(join_block).mediantime
        parameters = community.parameters
        expiration_date = join_date + parameters['sigValidity']
        current_time = time.time()
        return expiration_date - current_time

    def reload(self, func, community):
        '''
        Reload a cached property of this person in a community.
        This method is thread safe.
        This method clears the cache entry for this community and get it back.

        :param func: The cached property to reload
        :param community: The community to request for data
        :return: True if a changed was made by the reload.
        '''
        self._cache_mutex.lock()
        change = False
        try:
            if community.currency not in self._cache:
                self._cache[community.currency] = {}

            try:
                before = self._cache[community.currency][func.__name__]
            except KeyError:
                change = True

            try:
                value = func(self, community)

                if not change:
                    if type(value) is dict:
                        hash_before = (str(tuple(frozenset(sorted(before.keys())))),
                                     str(tuple(frozenset(sorted(before.items())))))
                        hash_after = (str(tuple(frozenset(sorted(value.keys())))),
                                     str(tuple(frozenset(sorted(value.items())))))
                        change = hash_before != hash_after
                    elif type(value) is bool:
                        change = before != value
                self._cache[community.currency][func.__name__] = value
            except Error:
                return False
        finally:
            self._cache_mutex.unlock()
        return change

    def jsonify(self):
        '''
        Get the community as dict in json format.
        :return: The community as a dict in json format
        '''
        data = {'uid': self.uid,
                'pubkey': self.pubkey,
                'cache': self._cache}
        return data

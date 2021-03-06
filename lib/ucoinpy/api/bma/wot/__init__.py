#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
# Caner Candan <caner@candan.fr>, http://caner.candan.fr
#

from .. import API, logging

logger = logging.getLogger("ucoin/wot")


class WOT(API):
    def __init__(self, connection_handler, module='wot'):
        super(WOT, self).__init__(connection_handler, module)


class Add(WOT):
    """POST Public key data."""

    def __post__(self, **kwargs):
        assert 'pubkey' in kwargs
        assert 'self_' in kwargs
        assert 'other' in kwargs

        return self.requests_post('/add', **kwargs).json()


class Revoke(WOT):
    """POST Public key data."""

    def __post__(self, **kwargs):
        assert 'pubkey' in kwargs
        assert 'self_' in kwargs

        return self.requests_post('/revoke', **kwargs).json()


class Lookup(WOT):
    """GET Public key data."""

    def __init__(self, connection_handler, search, module='wot'):
        super(WOT, self).__init__(connection_handler, module)

        self.search = search

    def __get__(self, **kwargs):
        assert self.search is not None

        return self.requests_get('/lookup/%s' % self.search, **kwargs).json()


class CertifiersOf(WOT):
    """GET Certification data over a member."""

    def __init__(self, connection_handler, search, module='wot'):
        super(WOT, self).__init__(connection_handler, module)

        self.search = search

    def __get__(self, **kwargs):
        assert self.search is not None

        return self.requests_get('/certifiers-of/%s' % self.search, **kwargs).json()


class CertifiedBy(WOT):
    """GET Certification data from a member."""

    def __init__(self, connection_handler, search, module='wot'):
        super(WOT, self).__init__(connection_handler, module)

        self.search = search

    def __get__(self, **kwargs):
        assert self.search is not None

        return self.requests_get('/certified-by/%s' % self.search, **kwargs).json()


class Members(WOT):
    """GET List all current members of the Web of Trust."""

    def __init__(self, connection_handler, module='wot'):
        super(WOT, self).__init__(connection_handler, module)

    def __get__(self, **kwargs):
        return self.requests_get('/members', **kwargs).json()

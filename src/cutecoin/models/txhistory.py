"""
Created on 5 févr. 2014

@author: inso
"""

import datetime
import logging
from ..core import money
from ..core.transfer import Transfer
from PyQt5.QtCore import QAbstractTableModel, Qt, QVariant, QSortFilterProxyModel, \
    QDateTime, QLocale, QModelIndex

from PyQt5.QtGui import QFont, QColor


class TxFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, ts_from, ts_to, parent=None):
        super().__init__(parent)
        self.community = None
        self.app = None
        self.ts_from = ts_from
        self.ts_to = ts_to
        self.payments = 0
        self.deposits = 0

    @property
    def account(self):
        return self.app.current_account

    def set_period(self, ts_from, ts_to):
        """
        Filter table by given timestamps
        """
        logging.debug("Filtering from {0} to {1}".format(
            datetime.datetime.fromtimestamp(ts_from).isoformat(' '),
            datetime.datetime.fromtimestamp(ts_to).isoformat(' '))
        )
        self.ts_from = ts_from
        self.ts_to = ts_to
        self.modelReset.emit()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        def in_period(date_ts):
            return date_ts in range(self.ts_from, self.ts_to)

        source_model = self.sourceModel()
        date_col = source_model.columns_types.index('date')
        source_index = source_model.index(sourceRow, date_col)
        date = source_model.data(source_index, Qt.DisplayRole)
        if in_period(date):
            # calculate sum total payments
            payment = source_model.data(
                source_model.index(sourceRow, source_model.columns_types.index('payment')),
                Qt.DisplayRole
            )
            if payment:
                self.payments += int(payment)
            # calculate sum total deposits
            deposit = source_model.data(
                source_model.index(sourceRow, source_model.columns_types.index('deposit')),
                Qt.DisplayRole
            )
            if deposit:
                self.deposits += int(deposit)

        return in_period(date)

    def columnCount(self, parent):
        return self.sourceModel().columnCount(None) - 4

    def setSourceModel(self, sourceModel):
        self.community = sourceModel.community
        self.app = sourceModel.app
        super().setSourceModel(sourceModel)

    def lessThan(self, left, right):
        """
        Sort table by given column number.
        """
        source_model = self.sourceModel()
        left_data = source_model.data(left, Qt.DisplayRole)
        right_data = source_model.data(right, Qt.DisplayRole)
        if left_data == "":
            return self.sortOrder() == Qt.DescendingOrder
        elif right_data == "":
            return self.sortOrder() == Qt.AscendingOrder
        if left_data == right_data:
            txid_col = source_model.columns_types.index('txid')
            txid_left = source_model.index(left.row(), txid_col)
            txid_right = source_model.index(right.row(), txid_col)
            return (txid_left < txid_right)

        return (left_data < right_data)

    def data(self, index, role):
        source_index = self.mapToSource(index)
        model = self.sourceModel()
        source_data = model.data(source_index, role)
        state_col = model.columns_types.index('state')
        state_index = model.index(source_index.row(), state_col)
        state_data = model.data(state_index, Qt.DisplayRole)
        if role == Qt.DisplayRole:
            if source_index.column() == model.columns_types.index('uid'):
                return source_data
            if source_index.column() == model.columns_types.index('date'):
                return QLocale.toString(
                    QLocale(),
                    QDateTime.fromTime_t(source_data).date(),
                    QLocale.dateFormat(QLocale(), QLocale.ShortFormat)
                )
            if source_index.column() == model.columns_types.index('payment') or \
                    source_index.column() == model.columns_types.index('deposit'):
                if source_data is not "":
                    return self.account.current_ref(source_data, self.community, self.app).diff_localized(international_system=True)

        if role == Qt.FontRole:
            font = QFont()
            if state_data == Transfer.AWAITING:
                font.setItalic(True)
            elif state_data == Transfer.REFUSED:
                font.setItalic(True)
            elif state_data == Transfer.TO_SEND:
                font.setBold(True)
            else:
                font.setItalic(False)
            return font

        if role == Qt.ForegroundRole:
            if state_data == Transfer.REFUSED:
                return QColor(Qt.red)
            elif state_data == Transfer.TO_SEND:
                return QColor(Qt.blue)

        if role == Qt.TextAlignmentRole:
            if source_index.column() == self.sourceModel().columns_types.index(
                    'deposit') or source_index.column() == self.sourceModel().columns_types.index('payment'):
                return Qt.AlignRight | Qt.AlignVCenter
            if source_index.column() == self.sourceModel().columns_types.index('date'):
                return Qt.AlignCenter

        if role == Qt.ToolTipRole:
            if state_data == Transfer.VALIDATING:
                block_col = model.columns_types.index('block_number')
                block_index = model.index(source_index.row(), block_col)
                block_data = model.data(block_index, Qt.DisplayRole)
                return "{0} / {1} validations".format(self.community.network.latest_block_number - block_data,
                                                      self.app.preferences['data_validation'])

            if source_index.column() == self.sourceModel().columns_types.index('date'):
                return QDateTime.fromTime_t(source_data).toString(Qt.SystemLocaleLongDate)

        return source_data


class HistoryTableModel(QAbstractTableModel):
    """
    A Qt abstract item model to display communities in a tree
    """

    def __init__(self, app, community, parent=None):
        """
        Constructor
        """
        super().__init__(parent)
        self.app = app
        self.community = community
        self.account._current_ref
        self.transfers_data = []
        self.refresh_transfers()

        self.columns_types = (
            'date',
            'uid',
            'payment',
            'deposit',
            'comment',
            'state',
            'txid',
            'pubkey',
            'block_number'
        )

        self.column_headers = (
            self.tr('Date'),
            self.tr('UID/Public key'),
            self.tr('Payment'),
            self.tr('Deposit'),
            self.tr('Comment'),
            'State',
            'TXID',
            'Pubkey',
            'Block Number'
        )

    @property
    def account(self):
        return self.app.current_account

    @property
    def transfers(self):
        return self.account.transfers(self.community) + self.account.dividends(self.community)

    def data_received(self, transfer):
        amount = transfer.metadata['amount']
        comment = ""
        if transfer.metadata['comment'] != "":
            comment = transfer.metadata['comment']
        if transfer.metadata['issuer_uid'] != "":
            sender = transfer.metadata['issuer_uid']
        else:
            sender = "pub:{0}".format(transfer.metadata['issuer'][:5])

        date_ts = transfer.metadata['time']
        txid = transfer.metadata['txid']
        block_number = transfer.metadata['block']

        return (date_ts, sender, "", amount,
                comment, transfer.state, txid,
                transfer.metadata['issuer'], block_number)

    def data_sent(self, transfer):
        amount = transfer.metadata['amount']
        comment = ""
        if transfer.metadata['comment'] != "":
            comment = transfer.metadata['comment']
        if transfer.metadata['receiver_uid'] != "":
            receiver = transfer.metadata['receiver_uid']
        else:
            receiver = "pub:{0}".format(transfer.metadata['receiver'][:5])

        date_ts = transfer.metadata['time']
        txid = transfer.metadata['txid']
        block_number = transfer.metadata['block']

        return (date_ts, receiver, amount,
                "", comment, transfer.state, txid,
                transfer.metadata['receiver'], block_number)

    def data_dividend(self, dividend):
        amount = dividend['amount']
        comment = ""
        receiver = self.account.name
        date_ts = dividend['time']
        id = dividend['id']
        return (date_ts, receiver, "",
                amount, "", Transfer.VALIDATED, id,
                self.account.pubkey)

    def refresh_transfers(self):
        self.beginResetModel()
        self.transfers_data = []
        for transfer in self.transfers:
            if type(transfer) is Transfer:
                if transfer.metadata['issuer'] == self.account.pubkey:
                    self.transfers_data.append(self.data_sent(transfer))
                else:
                    self.transfers_data.append(self.data_received(transfer))
            elif type(transfer) is dict:
                self.transfers_data.append(self.data_dividend(transfer))
        self.endResetModel()

    def rowCount(self, parent):
        return len(self.transfers_data)

    def columnCount(self, parent):
        return len(self.columns_types)

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if self.columns_types[section] == 'payment' or self.columns_types[section] == 'deposit':
                return '{:}\n({:})'.format(
                    self.column_headers[section],
                    self.account.current_ref.diff_units(self.community.short_currency)
                )

            return self.column_headers[section]

    def data(self, index, role):
        row = index.row()
        col = index.column()

        if not index.isValid():
            return QVariant()

        if role == Qt.DisplayRole:
            return self.transfers_data[row][col]

        if role == Qt.ToolTipRole and col == 0:
            return self.transfers_data[self.columns_types.index('date')]

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled


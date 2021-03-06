
import datetime

from PyQt5.QtWidgets import QDialog

from ..core.graph import Graph
from ..gen_resources.member_uic import Ui_DialogMember
from ..tools.exceptions import MembershipNotFoundError

class MemberDialog(QDialog, Ui_DialogMember):
    """
    classdocs
    """

    def __init__(self, account, community, person):
        """
        Constructor
        """
        super().__init__()
        self.setupUi(self)
        self.community = community
        self.account = account
        self.person = person
        self.label_uid.setText(person.uid)

        try:
            join_date = self.person.get_join_date(self.community)
        except MembershipNotFoundError:
            join_date = None

        if join_date is None:
            join_date = self.tr('not a member')
        else:
            join_date = datetime.datetime.fromtimestamp(join_date).strftime("%d/%m/%Y %I:%M")

        # calculate path to account member
        graph = Graph(self.community)
        path = None
        # if selected member is not the account member...
        if person.pubkey != self.account.pubkey:
            # add path from selected member to account member
            path = graph.get_shortest_path_between_members(person, self.account.get_person())

        text = self.tr("""
            <table cellpadding="5">
            <tr><td align="right"><b>{:}</b></div></td><td>{:}</td></tr>
            <tr><td align="right"><b>{:}</b></div></td><td>{:}</td></tr>
            """).format(
                self.tr('Public key'),
                self.person.pubkey,
                self.tr('Join date'),
                join_date
            )

        if path:
            distance = len(path) - 1
            text += self.tr("""<tr><td align="right"><b>{:}</b></div></td><td>{:}</td></tr>""".format(self.tr('Distance'), distance))
            if distance > 1:
                index = 0
                for node in path:
                    if index == 0:
                        text += self.tr("""<tr><td align="right"><b>{:}</b></div></td><td>{:}</td></tr>""").format(self.tr('Path'), node['text'])
                    else:
                        text += self.tr("""<tr><td align="right"><b>{:}</b></div></td><td>{:}</td></tr>""").format('', node['text'])
                    if index == distance and node['id'] != self.account.pubkey:
                        text += self.tr("""<tr><td align="right"><b>{:}</b></div></td><td>{:}</td></tr>""").format('', self.account.name)
                    index += 1
        # close html text
        text += "</table>"

        # set text in label
        self.label_properties.setText(text)


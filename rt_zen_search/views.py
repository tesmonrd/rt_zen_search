import re
from distutils.util import strtobool
from flask import abort
from itertools import chain
from sqlalchemy import cast, or_, Text
from sqlalchemy.sql.expression import false, true
from rt_zen_search.models import Organizations, Users, Tickets
from rt_zen_search.table_formatter import OrgTable, UserTable, TicketTable


tbl_map = {
	'org_id': [Organizations, OrgTable],
	'user_id': [Users, UserTable],
	'ticket_id': [Tickets, TicketTable]
}
id_field_mod = ['_id', 'org_id', 'user_id', 'ticket_id']
sql_arr_mod = ['domain_names', 'tags', 'query_all']
type_bool_mod = ['shared_tickets', 'active', 'verified',
	'shared', 'suspended', 'has_incidents'
]
type_int_mod = ['organization_id', 'submitter_id', 'assignee_id']


def process_query(query_data):
	"""Handles query processing calls and builds output."""
	if validated_general([*query_data.values()]):
		if 'query_all' in query_data:
			results = []
			if len(query_data['query_all'].split(',')) > 1:
				multi_search_val = [w.strip() for w in query_data['query_all'].split(',')]
				for s_t in multi_search_val:
					new_data = clean_and_execute(
						{'query_all': s_t}, [v[0] for k, v in tbl_map.items()]
					)
					if not results:
						results += new_data
					else:
						results = [x[0] + x[1] for x in zip(results, new_data)]
			else:
				results = clean_and_execute(query_data, [v[0] for k, v in tbl_map.items()])

			if not any(results):
				return None
			res_table = [
				OrgTable(results[0]),
				UserTable(results[1]),
				TicketTable(results[2])
			]
			return res_table

		elif any(key in id_field_mod for key in query_data.keys()):
			for k in tbl_map.keys():
				if k in query_data.keys():
					results = clean_and_execute(query_data, tbl_map[k][0])
					if not any(results):
						return None
					res_table = [tbl_map[k][1](results)]
					return res_table

		elif not all(query_data.values()):
			return None

		else:
			abort(400)
	else:
		return None


def clean_and_execute(query_data, db_table):
	"""Cleans and calls execution."""
	if isinstance(db_table, list):
		orgs = []
		users = []
		tickets = []

		for table in db_table:
			column_names = table.__table__.c.keys()
			if table == Tickets:
				column_names = ['ticket_id' if x == '_id' else x for x in column_names]
			if 'true' in query_data['query_all'].lower() or 'false' in query_data['query_all'].lower():
				column_names = [bool_f for bool_f in column_names if bool_f in type_bool_mod]

			mapped_data = {k: query_data['query_all'] for k in column_names}
			cleaned_data = data_corrections(
				{k: v for k, v in mapped_data.items() if v != ''}
				)

			if table.__table__.name == 'organizations':
				orgs.append(execute_queries(cleaned_data, table))
			elif table.__table__.name == 'users':
				users.append(execute_queries(cleaned_data, table))
			elif table.__table__.name == 'tickets':
				tickets.append(execute_queries(cleaned_data, table))
		result_data = orgs + users + tickets
		return result_data

	else:
		cleaned_data = data_corrections(
			{k: v for k, v in query_data.items() if v != ''}
		)
		result_data = execute_queries(cleaned_data, db_table, True)
		return result_data


def execute_queries(cleaned_data, db_table, and_filter=False):
	"""Executes queries on the Postgres DB."""
	result_data = []
	for attr, value in cleaned_data.items():
		if attr in type_int_mod or attr in type_bool_mod or attr == '_id':
			result_data.append(
				db_table.query.filter(getattr(db_table, attr).__eq__(value)).all()
			)
		elif attr in sql_arr_mod:
			result_data.append(
				db_table.query.filter(or_(*[cast(getattr(db_table, attr), Text).contains(x) for x in value])).all()
			)
		else:
			result_data.append(
				db_table.query.filter(getattr(db_table, attr).ilike(value)).all()
			)

	if and_filter and len(result_data) > 1:
		match = []
		comp = result_data[0]
		data = list(chain.from_iterable(result_data[1:]))
		for item in comp:
			if item in data:
				match.append(item)
		result_data = match
		return result_data

	flattened_data = list(chain.from_iterable(result_data))
	return flattened_data


def data_corrections(cleaned_data):
	"""Correct type issues and handle field modifications."""
	try:
		cleaned_keys = cleaned_data.keys()
		for id_mod in id_field_mod:
			if id_mod in cleaned_keys and 'ticket_id' not in cleaned_keys:
				if not cleaned_data[id_mod].isdigit():
					del cleaned_data[id_mod]
				else:
					cleaned_data['_id'] = int(cleaned_data.pop(id_mod))
			if id_mod in cleaned_keys:
				cleaned_data['_id'] = cleaned_data.pop(id_mod)

		for sql_mod in sql_arr_mod:
			if sql_mod in cleaned_keys:
				cleaned_data[sql_mod] = cleaned_data[sql_mod].split(",")

		for int_mod in type_int_mod:
			if int_mod in cleaned_keys:
				if not cleaned_data[int_mod].isdigit():
					del cleaned_data[int_mod]
				else:
					cleaned_data[int_mod] = int(cleaned_data[int_mod])

		for bool_mod in type_bool_mod:
			if bool_mod in cleaned_keys:
				try:
					if strtobool(cleaned_data[bool_mod]) == 0:
						cleaned_data[bool_mod] = false()
					else:
						cleaned_data[bool_mod] = true()
				except ValueError:
					del cleaned_data[bool_mod]

		return cleaned_data

	except KeyError as e:
		return "Invalid key passed in data: {}".format(e)


def validated_general(query_data):
	"""Basic check for unsafe characters in search."""
	regex = re.compile(r'[#$%^&*<>?\\|}{~:]')
	valid = False
	for data in query_data:
		if bool(regex.search(data)):
			valid = False
		else:
			valid = True
	return valid

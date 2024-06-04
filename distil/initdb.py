# Copyright (C) 2013-2024 Catalyst Cloud Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from models import Base
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool


def provision(engine):

    Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
    import argparse
    a = argparse.ArgumentParser()
    a.add_argument("-uri", "--db_uri", dest="uri", help="Database URI.")

    args = a.parse_args()

    engine = create_engine(args.uri, poolclass=NullPool)
    provision(engine)

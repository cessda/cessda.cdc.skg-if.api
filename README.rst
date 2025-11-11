CESSDA Data Catalogue SKG-IF API
================================

.. image:: https://github.com/EOSC-synergy/SQAaaS/raw/master/badges/badges_150x116/badge_software_bronze.png
   :target: https://api.eu.badgr.io/public/assertions/8Q924fqxT6mRZmqA3jV0hw
   :alt: SQAaaS badge

Provide studies as SKG-IF Products via API by transforming metadata stored in MongoDB.

Installation
------------

.. code-block:: bash

   pip install -r requirements.txt
   pip install .


Usage
-----

To run the CDC SKG-IF API, you can use the following command:

.. code-block:: bash

   uvicorn cessda_skgif_api.main:app --reload --host 0.0.0.0 --port 8000


Dependencies & requirements
---------------------------

* Python 3.8. or newer

The software is continuously tested against supported Python versions.

**Python packages**

The following can be obtained from Python package index.

* ConfigArgParse (License: MIT)
* FastAPI (License: MIT)
* Uvicorn (License: BSD 3-Clause)
* Pydantic (License: MIT)
* PyMongo (License: Apache 2.0)

License
-------

CESSDA Data Catalogue SKG-IF API is available under the Apache 2.0. See LICENSE.txt for the full license.

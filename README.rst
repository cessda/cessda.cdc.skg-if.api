CESSDA Data Catalogue SKG-IF API
================================

.. image:: https://github.com/EOSC-synergy/SQAaaS/raw/master/badges/badges_150x116/badge_software_bronze.png
   :target: https://api.eu.badgr.io/public/assertions/8Q924fqxT6mRZmqA3jV0hw
   :alt: SQAaaS badge

Exposes topics in ELSST (European Language Social Science Thesaurus) as SKG-IF Topics and studies in CDC as SKG-IF Products via API.
Studies are provided by transforming metadata stored in MongoDB of CDC Aggregator. This doesn't directly depend on any CDC Aggregator repositories but it assumes that the database collection has been populated by cessda.cdc.aggregator.client.
This server is designed for interoperability with CESSDA SKG-IF compliant clients and services.

Installation
------------

It is recommended to install the application inside a Python virtual environment to avoid conflicts with system packages.

.. code-block:: bash

   # Navigate to the directory where you want to keep virtual environments (outside the project directory)
   cd ~

   # Create a virtual environment
   python3 -m venv cessda-skgif-env

   # Activate the virtual environment
   source cessda-skgif-env/bin/activate

   # Navigate to the project directory
   cd /path/to/cessda.cdc.skg-if.api

   # Install dependencies
   pip install -r requirements.txt
   pip install .

   # Create and edit configuration file
   cp cessda_skgif_api.ini.dist cessda_skgif_api.ini
   nano cessda_skgif_api.ini

Usage
-----

To run the CDC SKG-IF API, you can use the following command:

.. code-block:: bash

   uvicorn cessda_skgif_api.main:app --reload --host 0.0.0.0 --port 8000

Or to run with gunicorn in a production setting:

.. code-block:: bash

   gunicorn -w 4 -k uvicorn.workers.UvicornWorker cessda_skgif_api.main:app

Running with Docker
-------------------

You can also run the CDC SKG-IF API using Docker that runs the app with gunicorn:

.. code-block:: bash

   # Build the Docker image
   docker buildx build . -t cessda/skg-if-api

   # Run the container
   docker run -d --network host cessda/skg-if-api

Static files
------------

The directory `static` should be served by Apache or Nginx under the same path prefix as the API.

Example Apache configuration with project directory in user apps home directory:

.. code-block:: apache
    # This is important to allow encoded slashes in topic IDs (URIs)
    AllowEncodedSlashes NoDecode

    <Location /api>
        ProxyPass http://localhost:8000 retry=3
        ProxyPassReverse http://localhost:8000
        Require all granted
        ProxyPreserveHost On
    </Location>

    Alias /api/static /home/apps/cessda.cdc.skg-if.api/static
    <Directory /home/apps/cessda.cdc.skg-if.api/static>
        Require all granted
    </Directory>

    <Location /api/static>
        ProxyPass !
    </Location>

Dependencies & requirements
---------------------------

* Python 3.10 or newer
* An ASGI server like Uvicorn or Gunicorn.
* An ELSST SKOS export in JSON-LD format (e.g., `elsst_current.jsonld`) placed in the `data/` directory.

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

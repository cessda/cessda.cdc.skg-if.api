CESSDA Data Catalogue SKG-IF API
================================

Provides studies as SKG-IF Products via API by transforming metadata stored in MongoDB.

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

Running with Docker
-------------------

You can also run the CDC SKG-IF API using Docker:

.. code-block:: bash

   # Build the Docker image
   docker buildx build . -t cessda/skg-if-api

   # Run the container
   docker run -d -p 8000:8000 cessda/skg-if-api

Dependencies & requirements
---------------------------

* Python 3.10 or newer

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

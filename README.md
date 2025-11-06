## technical_take_home
### Setup
- Step 1: to create conda env:
```conda env create -f environment.yml```

- Step 2: to activate conda env:
```conda activate tth```

- Step 3: to run streamlit app:
```streamlit run app.py --server.port 3000   ```






### Sources:
- ```https://www.youtube.com/watch?v=hn2WqRX75DI ```
streamlit template

- ```https://github.com/opengeos/streamlit-map-template ```
template source code

- ```https://www.youtube.com/watch?v=XDCB0uBCKMk```
plotly usage

- ```https://docs.streamlit.io/develop/api-reference/charts/st.area_chart ```
streamlit docs

- ```https://www.youtube.com/watch?v=o8p7uQCGD0U ```
streamlit help


### AI prompts (chatgpt): (reduced for clarity)

- what is the prefix in this file for?
- use conda
- the map is super zoomed out and shows the whole globe. just show the parking lot and make the each of the dots smaller
- waht about leafmap? ir is pydeck better
- i want to use this repo as a template and i want to just keep the marker cluster page for now make my thign for the marker clutster bere is the repo copy it exactly if you want: https:/github.com/opengeos/streamlit-map-template#

- edit it so that it starts zoomed in perfectly on carpoark with all the markers showing also. make it so the markers dont group togheter when they are close together .give me only the pythin script back

- here is a different single script streamlit app. combine the map from the current one (folium implementation) but use everyhting else, all other code, all data graphs, all website formatting, from the new one im showing you. combine them togehter like this.

- CSV with data structured like this: bay_id license_plate latitude longitude arrival_time duration_seconds,  handle the NULL (number plate data missing from the row) and outliar lang and lat coords (use an IQR threshold)? make a new tab on the website that shows rejected ones

- in the rejected rows tab, make another table that shows all numberplates that appear in the data set multiple times, such as a car re entering. dont exclude these datapoints, just include them in a table and call it: Cars with multikple entries or something better

- how to delete conda envs
- how to see my conda envs

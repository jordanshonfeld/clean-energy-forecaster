import logo from './logo.svg';
import './App.css';
import React, { useState, useEffect } from 'react';



function App() {
  const [data, setData] = useState(null);
  const [balancingAuthority, setBalancingAuthority] = useState("MISO");

useEffect(() => {
  console.log('Fetching data...');
  fetch('http://127.0.0.1:5000/api/app')
    .then(response => response.json())
    .then(json => {
      console.log('Data received:', json);
      setData(json);
    })
    .catch(error => console.error(error));
}, []);

const fetchData = async () => {
  try {
    console.log('Sending POST request with criteria:', balancingAuthority);
    const response = await fetch('http://127.0.0.1:5000/api/app', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({balancingAuthority}),
    });

    // Check if the response is successful (status code in the range 200-299)
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const json = await response.json();
    console.log('Data received:', json);
    setData(json);
  } catch (error) {
    console.error('Error fetching data:', error);
  }
};

const handleBalancingAuthorityChange = (event) => {
  setBalancingAuthority(event.target.value);
};

useEffect(() => {
  fetchData();
}, [balancingAuthority]); // Initial fetch when component mounts


const handleSubmit = (event) => {
  event.preventDefault();
  // Trigger fetch on form submission
  setData(null);
  fetchData();
};

// #69B34C --> green
// #ACB334 --> green-yellow
// #FAB733 --> yellow
// #FF8E15 --> orange
// #FF4E11 --> orange-red
// #FF0D0D --> red
// z score > 1 GREEN
// z score < 1 and > .5 green-yellow
// z score < .5 and >= 0 YELLOW
// z score <  0 > -.5 ORANGE
// z score < -.5 > -1 ORANGE-RED
// z score < -1 RED


  function processData(data){
        // let dataset = JSON.parse(data);
        const z_score_for_colors = data.z_score;        
        const sections = [];
        let colorString = "#69B34C";
        for(let i = 0; i < 24; i++){
          if(z_score_for_colors[i] >= 1){
            colorString = "#69B34C";
          } else if (z_score_for_colors[i] >= .5) {
            colorString = "#ACB334";
          } else if (z_score_for_colors[i] >= 0) {
            colorString = "#FAB733";
          } else if (z_score_for_colors[i] >= -.5){
            colorString = "#FF8E15"
          } else if (z_score_for_colors[i] >= -1.0){
            colorString = "#FF4E11"
          } else {
            colorString = "#FF0D0D"
          }
          //check z score for color... change string to "background-color:#XXXXXX"
          const time = i === 0? '12:00am': i > 12 ? i - 12 + ':00pm' : i + ':00am';
          sections.push(
            <React.Fragment key = {i}>
              <div className = "left">
                <h1>{time}</h1>
              </div>
              <div className = "right" id = {`right${i}`} style= {{backgroundColor: colorString}}></div>
              </React.Fragment>
          );
        }
        return(
          <div class = "timeline">
            {sections}
          </div>
        )
  }

  return (
    <div className="App">
      <header className="App-header">

      <h1>Today's Energy Forecast</h1>
      <form onSubmit={handleSubmit}>
          <label htmlFor="balancingAuthority">Balancing Authority: </label>
          <input
            type="text"
            id="balancingAuthority"
            value={balancingAuthority}
            onChange={handleBalancingAuthorityChange}
          />
          <button type="submit">Submit</button>
        </form>

        <p><a href="https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48">Find yours here!</a></p>
        <div class = "timeline-container">
        {data ? <pre>{processData(data)}</pre> : 'Loading...'}
      </div>


      </header>
    </div>
  );
}

export default App;

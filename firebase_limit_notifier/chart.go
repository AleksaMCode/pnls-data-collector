package main

import (
	"fmt"
	"log"
	"os"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/go-analyze/charts"
)

func generatePieChartInMemory(used float64, free float64) ([]byte, error) {
	values := []float64{used, free}
	labels := []string{"Used", "Free"}

	p, err := charts.PieRender(values,
		charts.LegendOptionFunc(charts.LegendOption{
			SeriesNames: labels,
			Offset:      charts.OffsetStr{Top: "55"},
		}),
		charts.TitleOptionFunc(charts.TitleOption{
			Text:    "PNLS-DC",
			Subtext: "Firebase Realtime DB Usage",
			Offset:  charts.OffsetCenter,
		}),
	)
	if err != nil {
		return nil, err
	}

	buf, err := p.Bytes()
	if err != nil {
		return nil, err
	}

	return buf, nil
}

func saveByteArrayToFile(filename string, pieChart []byte) {
	err := os.WriteFile(filename, pieChart, 0o644)
	if err != nil {
		logging.Fatal(fmt.Sprintf("Failed to save pie chart: %v", err))
	}
	log.Printf("Pie chart saved to %s", filename)
}

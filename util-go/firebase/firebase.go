package firebase

import (
	"context"
	"log"

	firebase "firebase.google.com/go/v4"
	"firebase.google.com/go/v4/db"
	"google.golang.org/api/option"
)

func GetFirebaseClient(ctx context.Context, credentials string, dbURL string) *db.Client {
	opt := option.WithCredentialsFile(credentials)
	conf := &firebase.Config{
		DatabaseURL: dbURL,
	}
	app, err := firebase.NewApp(ctx, conf, opt)
	if err != nil {
		log.Fatalf("Error initializing Firebase app: %v", err)
	}

	// Get a reference to the Realtime Database
	client, err := app.Database(ctx)
	if err != nil {
		log.Fatalf("Error getting database client: %v", err)
	}
	return client
}
